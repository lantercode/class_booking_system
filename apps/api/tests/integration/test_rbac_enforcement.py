"""
F1.1 RBAC 权限校验真实生效 - 集成测试

验证目标（对应 Feature 1.1 Acceptance Criteria）：
1. PERMISSION_CHECK_BYPASS=False 时，无权限用户访问受保护接口返回 403
2. 学员角色访问 /admin/* 返回 403
3. 所有写操作端点有 RBAC 装饰器（学员/教师角色边界）
4. 无 token 访问受保护接口返回 401
5. 调试端点（test-token / test-exception / test-auth）已删除返回 404
6. /ai/intents 需要认证

前置条件：
- 种子数据已由 conftest.seed_test_database 初始化
  （admin=13800000001 / teacher=13800138001 / student=13900139001，密码均为 Test@123456）
- Redis 可用（get_current_user 依赖黑名单检查）

运行方式：
    cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_rbac_enforcement.py -v
"""

import pytest
from httpx import AsyncClient

# 租户头：非白名单路径必须经过 TenantASGIMiddleware，缺少租户信息会被 400 拦截
TENANT_HEADERS = {"x-tenant-slug": "dance-school"}

# 种子账号（见 tests/conftest.py seed_test_database）
ADMIN_ACCOUNT = {"phone": "13800000001", "password": "Test@123456"}  # super_admin 角色
TEACHER_ACCOUNT = {"phone": "13800138001", "password": "Test@123456"}  # teacher 角色
STUDENT_ACCOUNT = {"phone": "13900139001", "password": "Test@123456"}  # student 角色


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


@pytest.fixture
async def admin_token(client: AsyncClient) -> str:
    return await _login(client, ADMIN_ACCOUNT)


@pytest.fixture
async def teacher_token(client: AsyncClient) -> str:
    return await _login(client, TEACHER_ACCOUNT)


@pytest.fixture
async def student_token(client: AsyncClient) -> str:
    return await _login(client, STUDENT_ACCOUNT)


class TestPermissionEnforcement:
    """AC：无权限用户访问受保护接口返回 403；学员访问 /admin/* 返回 403"""

    @pytest.mark.asyncio
    async def test_student_cannot_create_user(self, client: AsyncClient, student_token: str):
        """学员（仅 booking:view 权限）调用 POST /users/ → 403（需要 user:create）

        注意：user 模块的创建端点注册路径为 /users/（尾斜杠），
        后端 redirect_slashes=False，POST /users 会因 GET /users 存在而返回 405。
        """
        # 提供合法请求体以通过 Pydantic 校验，确保走到 RBAC 装饰器
        resp = await client.post(
            "/api/v1/users/",
            json={"phone": "13999999999", "password": "Test@123456"},
            headers=_headers(student_token),
        )
        assert resp.status_code == 403, f"期望 403，实际 {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_student_cannot_access_admin_users(self, client: AsyncClient, student_token: str):
        """学员访问 GET /admin/users → 403（需要 user:read）"""
        resp = await client.get("/api/v1/admin/users", headers=_headers(student_token))
        assert resp.status_code == 403, f"期望 403，实际 {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_admin_write_endpoint_passes_rbac(self, client: AsyncClient, admin_token: str):
        """super_admin 调用 DELETE /courses/{id} → 不被 RBAC 拦截（验证补权生效）

        super_admin 拥有全部权限（含 course:delete），权限校验应通过；
        后续业务结果视数据而定（课程不存在返回 404），但不能是 401/403。
        """
        resp = await client.delete("/api/v1/courses/999999", headers=_headers(admin_token))
        assert resp.status_code not in (401, 403), (
            f"admin 写端点不应被 RBAC 拦截，实际 {resp.status_code}: {resp.text}"
        )

    @pytest.mark.asyncio
    async def test_unauthenticated_request_returns_401(self, client: AsyncClient):
        """无 token 访问受保护端点 → 401"""
        resp = await client.get("/api/v1/users", headers=TENANT_HEADERS)
        assert resp.status_code == 401, f"期望 401，实际 {resp.status_code}: {resp.text}"


class TestRoleBoundaries:
    """AC：写操作端点的角色边界（booking 仅学员、teacher/me 仅教师、tenant/settings 仅管理员）"""

    @pytest.mark.asyncio
    async def test_student_passes_booking_role_check(self, client: AsyncClient, student_token: str):
        """学员 POST /bookings/ → 通过 require_roles("student")，不被 403 拦截

        排期 999999 不存在，业务层会返回错误，但状态码不能是 401/403。
        """
        resp = await client.post(
            "/api/v1/bookings/",
            json={"schedule_id": 999999},
            headers=_headers(student_token),
        )
        assert resp.status_code not in (401, 403), (
            f"学员预约不应被 RBAC 拦截，实际 {resp.status_code}: {resp.text}"
        )

    @pytest.mark.asyncio
    async def test_teacher_cannot_create_booking(self, client: AsyncClient, teacher_token: str):
        """教师 POST /bookings/ → 403（require_roles("student")）"""
        resp = await client.post(
            "/api/v1/bookings/",
            json={"schedule_id": 999999},
            headers=_headers(teacher_token),
        )
        assert resp.status_code == 403, f"期望 403，实际 {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_student_cannot_access_teacher_me(self, client: AsyncClient, student_token: str):
        """学员 GET /teachers/me → 403（require_roles("teacher")）"""
        resp = await client.get("/api/v1/teachers/me", headers=_headers(student_token))
        assert resp.status_code == 403, f"期望 403，实际 {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_student_cannot_access_tenant_settings(self, client: AsyncClient, student_token: str):
        """学员 GET /tenant/settings → 403（require_roles("admin","super_admin")）"""
        resp = await client.get("/api/v1/tenant/settings", headers=_headers(student_token))
        assert resp.status_code == 403, f"期望 403，实际 {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_admin_can_access_tenant_settings(self, client: AsyncClient, admin_token: str):
        """super_admin GET /tenant/settings → 不被 RBAC 拦截"""
        resp = await client.get("/api/v1/tenant/settings", headers=_headers(admin_token))
        assert resp.status_code not in (401, 403), (
            f"admin 访问租户配置不应被拦截，实际 {resp.status_code}: {resp.text}"
        )

    @pytest.mark.asyncio
    async def test_admin_can_access_admin_settings(self, client: AsyncClient, admin_token: str):
        """super_admin GET /admin/settings → 200（装饰器已改为 require_roles）"""
        resp = await client.get("/api/v1/admin/settings", headers=_headers(admin_token))
        assert resp.status_code == 200, f"期望 200，实际 {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_student_cannot_access_admin_settings(self, client: AsyncClient, student_token: str):
        """学员 GET /admin/settings → 403"""
        resp = await client.get("/api/v1/admin/settings", headers=_headers(student_token))
        assert resp.status_code == 403, f"期望 403，实际 {resp.status_code}: {resp.text}"


class TestDebugEndpointsRemoved:
    """AC：调试端点已删除（test-token 曾是严重安全漏洞：无认证可生成 admin JWT）"""

    @pytest.mark.asyncio
    async def test_test_token_endpoint_removed(self, client: AsyncClient):
        resp = await client.get("/api/v1/common/test-token", headers=TENANT_HEADERS)
        assert resp.status_code == 404, f"期望 404，实际 {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_test_exception_endpoint_removed(self, client: AsyncClient):
        resp = await client.get("/api/v1/common/test-exception", headers=TENANT_HEADERS)
        assert resp.status_code == 404, f"期望 404，实际 {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_test_auth_endpoint_removed(self, client: AsyncClient):
        resp = await client.get("/api/v1/common/test-auth", headers=TENANT_HEADERS)
        assert resp.status_code == 404, f"期望 404，实际 {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_health_endpoint_still_public(self, client: AsyncClient):
        """health 保持公开（在租户跳过白名单内，无需任何头）"""
        resp = await client.get("/api/v1/common/health")
        assert resp.status_code == 200, f"期望 200，实际 {resp.status_code}: {resp.text}"


class TestAiIntentsProtected:
    """AC：/ai/intents 暴露内部意图配置，必须认证"""

    @pytest.mark.asyncio
    async def test_intents_requires_authentication(self, client: AsyncClient):
        """无 token GET /ai/intents → 401"""
        resp = await client.get("/api/v1/ai/intents", headers=TENANT_HEADERS)
        assert resp.status_code == 401, f"期望 401，实际 {resp.status_code}: {resp.text}"

    @pytest.mark.asyncio
    async def test_intents_accessible_with_token(self, client: AsyncClient, student_token: str):
        """已认证用户 GET /ai/intents → 认证生效（不再 401）

        已知预存缺陷（与 F1.1 无关，登记为技术债 D-F1.1-1）：
        端点内部访问 `IntentRecognizer.intents`，但该类只有类属性 `INTENTS`
        （list[tuple] 结构），认证通过后会触发 AttributeError → 500。
        此处仅断言认证门槛生效（非 401），端点功能修复归 AI 模块另行处理。
        """
        resp = await client.get("/api/v1/ai/intents", headers=_headers(student_token))
        assert resp.status_code != 401, f"已认证请求不应返回 401，实际 {resp.status_code}: {resp.text}"
