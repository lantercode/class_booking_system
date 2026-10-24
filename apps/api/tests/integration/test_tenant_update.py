"""
F3.3 租户设置页 PUT 端点 - 集成测试

验证目标（对应 F3.3 Acceptance Criteria）：
1. admin/super_admin 可更新租户配置（PUT /api/v1/tenant/settings），GET 回读值一致
2. admin/super_admin 可更新租户基本信息（PUT /api/v1/tenant/info），GET 回读值一致
3. student 角色调用写端点 → 403（require_roles("admin","super_admin")）
4. 未认证请求 → 401
5. 非法入参（0 / 500 / 非数字字符串）→ 422（Pydantic 校验）
6. settings 浅合并语义：请求未传的键不被覆盖

前置条件：
- 种子数据已由 conftest.seed_test_database 初始化
  （super_admin=13800000001 / teacher=13800138001 / student=13900139001，密码 Test@123456）
- Redis 可用（get_current_user 依赖黑名单检查）
- 本文件额外创建 admin 角色用户（13800000002 / Test@123456）

运行方式：
    cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_tenant_update.py -v
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import hash_password
from app.modules.auth.models import Role, UserRole
from app.modules.tenant.models import Tenant
from app.modules.user.models import User, UserStatus

settings = get_settings()
TEST_DATABASE_URL = settings.DATABASE_URL

# 租户头：非白名单路径必须经过 TenantASGIMiddleware
TENANT_HEADERS = {"x-tenant-slug": "dance-school"}

# 种子账号（见 tests/conftest.py seed_test_database）
SUPER_ADMIN_ACCOUNT = {"phone": "13800000001", "password": "Test@123456"}  # super_admin
STUDENT_ACCOUNT = {"phone": "13900139001", "password": "Test@123456"}  # student
# 本文件 fixture 额外创建的 admin 角色账号
ADMIN_ACCOUNT = {"phone": "13800000002", "password": "Test@123456"}


async def _login(client: AsyncClient, account: dict) -> str:
    """登录并返回 access_token"""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"tenant_slug": "dance-school", **account},
    )
    assert resp.status_code == 200, f"登录失败: {resp.text}"
    body = resp.json()
    assert body["code"] == 0, f"登录业务失败: {body}"
    return body["data"]["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", **TENANT_HEADERS}


@pytest.fixture(scope="session", autouse=True)
async def ensure_admin_user(seed_test_database):
    """确保存在 admin 角色用户（13800000002 / Test@123456）

    conftest 种子数据仅创建了 super_admin / teacher / student 三个账号，
    本 fixture 在测试开始前补建一个 admin 角色用户，
    用于验证 require_roles("admin","super_admin") 的 OR 语义对 admin 角色生效。
    幂等：已存在则跳过。
    """
    engine = create_async_engine(
        TEST_DATABASE_URL, echo=False, pool_size=3, max_overflow=5, pool_pre_ping=True
    )
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        async with session_factory() as session:
            # 检查是否已存在
            result = await session.execute(
                select(User).where(User.phone == "13800000002")
            )
            existing = result.scalar_one_or_none()
            if existing:
                print("\n✅ admin 用户已存在，跳过创建")
                return

            # 获取租户
            tenant_result = await session.execute(
                select(Tenant).where(Tenant.slug == "dance-school")
            )
            tenant = tenant_result.scalar_one()

            # 获取 admin 角色
            role_result = await session.execute(
                select(Role).where(
                    Role.code == "admin", Role.tenant_id == tenant.id
                )
            )
            admin_role = role_result.scalar_one()

            # 创建 admin 用户
            user = User(
                tenant_id=tenant.id,
                phone="13800000002",
                password_hash=hash_password("Test@123456"),
                nickname="管理员",
                platform_role="admin",
                status=UserStatus.ACTIVE.value,
            )
            session.add(user)
            await session.flush()
            session.add(UserRole(user_id=user.id, role_id=admin_role.id))
            await session.commit()
            print("\n✅ 创建 admin 角色用户: 13800000002")
    finally:
        await engine.dispose()


@pytest.fixture
async def admin_token(client: AsyncClient) -> str:
    return await _login(client, ADMIN_ACCOUNT)


@pytest.fixture
async def super_admin_token(client: AsyncClient) -> str:
    return await _login(client, SUPER_ADMIN_ACCOUNT)


@pytest.fixture
async def student_token(client: AsyncClient) -> str:
    return await _login(client, STUDENT_ACCOUNT)


@pytest.fixture
async def restore_tenant_state():
    """保存并恢复租户状态，防止测试间数据污染

    仅对实际修改租户数据的测试生效（200 类测试）。
    403/401/422 类测试在到达 Service 前即被拦截，不会修改数据。
    """
    engine = create_async_engine(
        TEST_DATABASE_URL, echo=False, pool_size=3, max_overflow=5, pool_pre_ping=True
    )
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    # 保存原始状态
    async with session_factory() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.slug == "dance-school")
        )
        tenant = result.scalar_one()
        original = {
            "name": tenant.name,
            "logo_url": tenant.logo_url,
            "contact_phone": tenant.contact_phone,
            "contact_email": tenant.contact_email,
            "settings": dict(tenant.settings) if tenant.settings else {},
        }

    yield

    # 恢复原始状态
    async with session_factory() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.slug == "dance-school")
        )
        tenant = result.scalar_one()
        tenant.name = original["name"]
        tenant.logo_url = original["logo_url"]
        tenant.contact_phone = original["contact_phone"]
        tenant.contact_email = original["contact_email"]
        tenant.settings = original["settings"]
        await session.commit()

    await engine.dispose()


class TestUpdateSettings:
    """PUT /api/v1/tenant/settings - 租户配置更新"""

    @pytest.mark.asyncio
    async def test_admin_update_settings_success(
        self, client: AsyncClient, admin_token: str, restore_tenant_state
    ):
        """admin PUT /tenant/settings → 200，GET 回读值一致"""
        payload = {"booking_cancel_minutes": 60, "booking_advance_days": 7}
        resp = await client.put(
            "/api/v1/tenant/settings",
            json=payload,
            headers=_headers(admin_token),
        )
        assert resp.status_code == 200, f"期望 200，实际 {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["booking_cancel_minutes"] == 60
        assert data["booking_advance_days"] == 7

        # GET 回读验证
        get_resp = await client.get(
            "/api/v1/tenant/settings",
            headers=_headers(admin_token),
        )
        assert get_resp.status_code == 200
        get_data = get_resp.json()["data"]
        assert get_data["booking_cancel_minutes"] == 60
        assert get_data["booking_advance_days"] == 7

    @pytest.mark.asyncio
    async def test_settings_merge_semantics(
        self, client: AsyncClient, admin_token: str, restore_tenant_state
    ):
        """settings 浅合并：PUT 只传一个键时，另一个键保持不变"""
        # 1. 先设置两个字段
        await client.put(
            "/api/v1/tenant/settings",
            json={"booking_cancel_minutes": 30, "booking_advance_days": 5},
            headers=_headers(admin_token),
        )

        # 2. 只更新 cancel_minutes，不传 advance_days
        resp = await client.put(
            "/api/v1/tenant/settings",
            json={"booking_cancel_minutes": 120},
            headers=_headers(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["booking_cancel_minutes"] == 120
        # advance_days 应保持上一次的 5，而非默认 14
        assert data["booking_advance_days"] == 5

        # GET 回读再次确认
        get_resp = await client.get(
            "/api/v1/tenant/settings",
            headers=_headers(admin_token),
        )
        get_data = get_resp.json()["data"]
        assert get_data["booking_cancel_minutes"] == 120
        assert get_data["booking_advance_days"] == 5

    @pytest.mark.asyncio
    async def test_invalid_cancel_minutes_zero(
        self, client: AsyncClient, admin_token: str
    ):
        """booking_cancel_minutes=0 → 422（ge=1）"""
        resp = await client.put(
            "/api/v1/tenant/settings",
            json={"booking_cancel_minutes": 0},
            headers=_headers(admin_token),
        )
        assert resp.status_code == 422, f"期望 422，实际 {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_invalid_cancel_minutes_over_limit(
        self, client: AsyncClient, admin_token: str
    ):
        """booking_cancel_minutes=500 → 422（le=480）"""
        resp = await client.put(
            "/api/v1/tenant/settings",
            json={"booking_cancel_minutes": 500},
            headers=_headers(admin_token),
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_advance_days_zero(
        self, client: AsyncClient, admin_token: str
    ):
        """booking_advance_days=0 → 422（ge=1）"""
        resp = await client.put(
            "/api/v1/tenant/settings",
            json={"booking_advance_days": 0},
            headers=_headers(admin_token),
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_string_value(
        self, client: AsyncClient, admin_token: str
    ):
        """booking_cancel_minutes 传非数字字符串 → 422"""
        resp = await client.put(
            "/api/v1/tenant/settings",
            json={"booking_cancel_minutes": "abc"},
            headers=_headers(admin_token),
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_super_admin_can_update_settings(
        self, client: AsyncClient, super_admin_token: str, restore_tenant_state
    ):
        """super_admin 也能 PUT /tenant/settings（require_roles OR 语义）"""
        resp = await client.put(
            "/api/v1/tenant/settings",
            json={"booking_cancel_minutes": 100},
            headers=_headers(super_admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["booking_cancel_minutes"] == 100


class TestUpdateInfo:
    """PUT /api/v1/tenant/info - 租户基本信息更新"""

    @pytest.mark.asyncio
    async def test_super_admin_update_info_success(
        self, client: AsyncClient, super_admin_token: str, restore_tenant_state
    ):
        """super_admin PUT /tenant/info → 200，GET 回读值一致"""
        payload = {
            "name": "测试租户新名称",
            "logo_url": "https://example.com/logo.png",
            "contact_phone": "13900000000",
            "contact_email": "test@example.com",
        }
        resp = await client.put(
            "/api/v1/tenant/info",
            json=payload,
            headers=_headers(super_admin_token),
        )
        assert resp.status_code == 200, f"期望 200，实际 {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["name"] == "测试租户新名称"
        assert data["logo_url"] == "https://example.com/logo.png"
        assert data["contact_phone"] == "13900000000"
        assert data["contact_email"] == "test@example.com"

        # GET 回读验证
        get_resp = await client.get(
            "/api/v1/tenant/info",
            headers=_headers(super_admin_token),
        )
        assert get_resp.status_code == 200
        get_data = get_resp.json()["data"]
        assert get_data["name"] == "测试租户新名称"
        assert get_data["logo_url"] == "https://example.com/logo.png"
        assert get_data["contact_phone"] == "13900000000"
        assert get_data["contact_email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_info_partial_update_preserves_other_fields(
        self, client: AsyncClient, admin_token: str, restore_tenant_state
    ):
        """只传 name 时，logo_url 等字段不被覆盖为 None（update_info 只更新非 None 字段）"""
        # 先设置 logo_url
        await client.put(
            "/api/v1/tenant/info",
            json={"name": "有Logo的租户", "logo_url": "https://example.com/x.png"},
            headers=_headers(admin_token),
        )

        # 只更新 name，不传 logo_url
        resp = await client.put(
            "/api/v1/tenant/info",
            json={"name": "新名称2"},
            headers=_headers(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "新名称2"
        # logo_url 应保持上一次设置的值，不被覆盖为 None
        assert data["logo_url"] == "https://example.com/x.png"

    @pytest.mark.asyncio
    async def test_info_missing_name_returns_422(
        self, client: AsyncClient, admin_token: str
    ):
        """缺少必填字段 name → 422"""
        resp = await client.put(
            "/api/v1/tenant/info",
            json={"logo_url": "https://example.com/x.png"},
            headers=_headers(admin_token),
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_admin_can_update_info(
        self, client: AsyncClient, admin_token: str, restore_tenant_state
    ):
        """admin 也能 PUT /tenant/info（require_roles OR 语义）"""
        resp = await client.put(
            "/api/v1/tenant/info",
            json={"name": "admin更新的名称"},
            headers=_headers(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "admin更新的名称"


class TestAuthorization:
    """权限与认证校验"""

    @pytest.mark.asyncio
    async def test_student_cannot_update_settings(
        self, client: AsyncClient, student_token: str
    ):
        """student PUT /tenant/settings → 403"""
        resp = await client.put(
            "/api/v1/tenant/settings",
            json={"booking_cancel_minutes": 60},
            headers=_headers(student_token),
        )
        assert resp.status_code == 403, f"期望 403，实际 {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_student_cannot_update_info(
        self, client: AsyncClient, student_token: str
    ):
        """student PUT /tenant/info → 403"""
        resp = await client.put(
            "/api/v1/tenant/info",
            json={"name": "hack"},
            headers=_headers(student_token),
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_settings(self, client: AsyncClient):
        """未认证 PUT /tenant/settings → 401"""
        resp = await client.put(
            "/api/v1/tenant/settings",
            json={"booking_cancel_minutes": 60},
            headers=TENANT_HEADERS,
        )
        assert resp.status_code == 401, f"期望 401，实际 {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_unauthenticated_info(self, client: AsyncClient):
        """未认证 PUT /tenant/info → 401"""
        resp = await client.put(
            "/api/v1/tenant/info",
            json={"name": "hack"},
            headers=TENANT_HEADERS,
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_no_traceback_in_error_response(
        self, client: AsyncClient, student_token: str
    ):
        """输出安全：403 响应不包含 traceback / SQL / 内部堆栈"""
        resp = await client.put(
            "/api/v1/tenant/settings",
            json={"booking_cancel_minutes": 60},
            headers=_headers(student_token),
        )
        assert resp.status_code == 403
        body = resp.text.lower()
        assert "traceback" not in body
        assert "sql" not in body
        assert "select" not in body


class TestNoTrailingSlash:
    """端点不加尾斜杠（redirect_slashes=False）"""

    @pytest.mark.asyncio
    async def test_settings_trailing_slash_404(
        self, client: AsyncClient, admin_token: str
    ):
        """PUT /tenant/settings/ → 404（尾斜杠不匹配，无重定向）"""
        resp = await client.put(
            "/api/v1/tenant/settings/",
            json={"booking_cancel_minutes": 60},
            headers=_headers(admin_token),
        )
        assert resp.status_code == 404, f"期望 404，实际 {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_info_trailing_slash_404(
        self, client: AsyncClient, admin_token: str
    ):
        """PUT /tenant/info/ → 404（尾斜杠不匹配，无重定向）"""
        resp = await client.put(
            "/api/v1/tenant/info/",
            json={"name": "test"},
            headers=_headers(admin_token),
        )
        assert resp.status_code == 404
