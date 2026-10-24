"""
F2.2 预约数据归属与泄露修复 - 集成测试

验证目标（对应 Feature 2.2 Acceptance Criteria）：
- AC-1：学员按 schedule_id 查仍只看自己（修复 router 越权）
- AC-2：学员查他人预约详情 → 403
- AC-3：学员列表只返回自己
- AC-4：教师列表只返回其排期下的预约
- AC-5：教师查/拒他人排期预约详情（200 / 403）
- AC-6：管理员全量可查
- AC-8：Service 直调（MCP 等价路径）对 student 用户仍只返回自己
- AC-10：学员 owner 始终能查自己
- AC-11：不存在预约 → 404

前置条件：
- 种子数据已由 conftest.seed_test_database 初始化
  （super_admin=13800000001 / teacher=13800138001 / student=13900139001，密码 Test@123456）
- Redis 可用（RBAC 装饰器缓存）

运行方式：
    cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_booking_ownership.py -v
"""

import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.tenant_context import set_tenant_id
from app.modules.booking.models import Booking, BookingSource, BookingStatus
from app.modules.booking.service import BookingService
from app.modules.course.models import Course
from app.modules.schedule.models import CourseSchedule, ScheduleStatus
from app.modules.user.models import User

TENANT_HEADERS = {"x-tenant-slug": "dance-school"}
SUPER_ADMIN = {"phone": "13800000001", "password": "Test@123456"}  # super_admin
SEED_STUDENT_A = {"phone": "13900139001", "password": "Test@123456"}  # student 李同学
SEED_TEACHER_T = {"phone": "13800138001", "password": "Test@123456"}  # teacher 张老师

BASE = "/api/v1"


def _unique_phone() -> str:
    return f"139{(time.time_ns() // 1000 + uuid4().int) % 100000000:08d}"


async def _login(client: AsyncClient, account: dict) -> str:
    resp = await client.post(
        f"{BASE}/auth/login",
        json={"tenant_slug": "dance-school", **account},
    )
    assert resp.status_code == 200, f"登录失败: {resp.text}"
    body = resp.json()
    assert body["code"] == 0, f"登录业务失败: {body}"
    return body["data"]["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", **TENANT_HEADERS}


async def _get_role_id(client: AsyncClient, token: str, code: str) -> int:
    resp = await client.get(f"{BASE}/roles", headers=_headers(token))
    assert resp.status_code == 200, f"获取角色列表失败: {resp.text}"
    items = resp.json()["data"]["items"]
    return next(r["id"] for r in items if r["code"] == code)


async def _create_user(client: AsyncClient, token: str, role_code: str, username: str) -> dict:
    """通过 admin 端点创建带角色的真实用户（密码哈希、角色分配、profile 联动）"""
    role_id = await _get_role_id(client, token, role_code)
    payload = {
        "username": username,
        "phone": _unique_phone(),
        "password": "Test@123456",
        "is_active": True,
        "role_ids": [role_id],
    }
    resp = await client.post(f"{BASE}/admin/users", json=payload, headers=_headers(token))
    assert resp.status_code == 201, f"创建用户失败: {resp.text}"
    body = resp.json()
    assert body["code"] == 0, f"创建用户业务失败: {body}"
    return body["data"]


async def _lookup_user_id(client: AsyncClient, token: str, phone: str) -> int:
    resp = await client.get(
        f"{BASE}/admin/users", params={"keyword": phone}, headers=_headers(token)
    )
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    return next(u["id"] for u in items if u["phone"] == phone)


@pytest.fixture
async def admin_token(client: AsyncClient) -> str:
    return await _login(client, SUPER_ADMIN)


@pytest.fixture(scope="session")
async def booking_data(live_server):
    """搭建归属测试数据（session 级，全用例共享）：2 学员 / 2 教师 / 2 排期 / 3 预约

    - 学员 A（种子 13900139001）
    - 学员 B（新建）
    - 教师 T（种子 13800138001，schedule_T 的授课教师）
    - 教师 T2（新建，schedule_T2 的授课教师）
    - 排期 schedule_T（teacher=T）、schedule_T2（teacher=T2），均容量 5、未来 3 天
    - 预约：
        booking_A_on_T  : A 在 schedule_T
        booking_B_on_T  : B 在 schedule_T
        booking_A_on_T2 : A 在 schedule_T2（教师 T 不应看到）

    学员 B / 教师 T2 经 admin HTTP 创建（密码哈希/角色/profile 由 Service 处理）；
    课程/排期/预约经独立提交会话直接落库（聚焦读归属测试，绕过 create 链路）。
    """
    async with AsyncClient(base_url=live_server) as setup_client:
        admin_token = await _login(setup_client, SUPER_ADMIN)

        settings = get_settings()
        engine = create_async_engine(
            settings.DATABASE_URL, echo=False, pool_size=3, max_overflow=5, pool_pre_ping=True
        )
        session_factory = async_sessionmaker(
            bind=engine, class_=AsyncSession, expire_on_commit=False
        )

        # 1. 查租户与种子用户 ID
        async with session_factory() as session:
            from app.modules.tenant.models import Tenant

            tenant = (
                await session.execute(select(Tenant).where(Tenant.slug == "dance-school"))
            ).scalar_one()
            tenant_id = tenant.id
            a_id = (
                await session.execute(
                    select(User).where(User.phone == SEED_STUDENT_A["phone"])
                )
            ).scalar_one().id
            t_id = (
                await session.execute(
                    select(User).where(User.phone == SEED_TEACHER_T["phone"])
                )
            ).scalar_one().id

        # 2. 经 admin HTTP 创建学员 B、教师 T2
        student_b = await _create_user(setup_client, admin_token, "student", "归属测试学员B")
        teacher_t2 = await _create_user(setup_client, admin_token, "teacher", "归属测试教师T2")
        b_id = await _lookup_user_id(setup_client, admin_token, student_b["phone"])
        t2_id = await _lookup_user_id(setup_client, admin_token, teacher_t2["phone"])

        # 3. 直接落库：课程 + 2 排期 + 3 预约
        start = datetime.now(UTC) + timedelta(days=3)
        created_course_ids: list[int] = []
        created_schedule_ids: list[int] = []
        created_booking_ids: list[int] = []

        async with session_factory() as session:
            set_tenant_id(tenant_id)
            course = Course(
                tenant_id=tenant_id,
                name=f"归属测试课程{uuid4().hex[:6]}",
                duration_minutes=60,
            )
            session.add(course)
            await session.flush()
            created_course_ids.append(course.id)

            schedule_t = CourseSchedule(
                tenant_id=tenant_id,
                course_id=course.id,
                teacher_id=t_id,
                start_at=start,
                end_at=start + timedelta(hours=1),
                capacity=5,
                status=ScheduleStatus.NORMAL.value,
            )
            schedule_t2 = CourseSchedule(
                tenant_id=tenant_id,
                course_id=course.id,
                teacher_id=t2_id,
                start_at=start + timedelta(hours=2),
                end_at=start + timedelta(hours=3),
                capacity=5,
                status=ScheduleStatus.NORMAL.value,
            )
            session.add_all([schedule_t, schedule_t2])
            await session.flush()
            created_schedule_ids.extend([schedule_t.id, schedule_t2.id])

            booking_a_on_t = Booking(
                tenant_id=tenant_id,
                schedule_id=schedule_t.id,
                student_id=a_id,
                status=BookingStatus.BOOKED.value,
                source=BookingSource.SELF.value,
            )
            booking_b_on_t = Booking(
                tenant_id=tenant_id,
                schedule_id=schedule_t.id,
                student_id=b_id,
                status=BookingStatus.BOOKED.value,
                source=BookingSource.SELF.value,
            )
            booking_a_on_t2 = Booking(
                tenant_id=tenant_id,
                schedule_id=schedule_t2.id,
                student_id=a_id,
                status=BookingStatus.BOOKED.value,
                source=BookingSource.SELF.value,
            )
            session.add_all([booking_a_on_t, booking_b_on_t, booking_a_on_t2])
            await session.flush()
            created_booking_ids.extend(
                [booking_a_on_t.id, booking_b_on_t.id, booking_a_on_t2.id]
            )
            await session.commit()

    data = {
        "tenant_id": tenant_id,
        "a_id": a_id,
        "b_id": b_id,
        "t_id": t_id,
        "t2_id": t2_id,
        "schedule_t_id": created_schedule_ids[0],
        "schedule_t2_id": created_schedule_ids[1],
        "booking_a_on_t_id": created_booking_ids[0],
        "booking_b_on_t_id": created_booking_ids[1],
        "booking_a_on_t2_id": created_booking_ids[2],
        "b_phone": student_b["phone"],
        "t2_phone": teacher_t2["phone"],
    }

    yield data

    # 4. 清理：先 DB 删预约/排期/课程（避免教师未来排期阻塞用户软删）→ 再软删用户
    async with session_factory() as session:
        set_tenant_id(tenant_id)
        await session.execute(
            delete(Booking).where(Booking.id.in_(created_booking_ids))
        )
        await session.execute(
            delete(CourseSchedule).where(CourseSchedule.id.in_(created_schedule_ids))
        )
        await session.execute(delete(Course).where(Course.id.in_(created_course_ids)))
        await session.commit()
    await engine.dispose()

    async with AsyncClient(base_url=live_server) as cleanup_client:
        tok = await _login(cleanup_client, SUPER_ADMIN)
        for phone in (data["b_phone"], data["t2_phone"]):
            try:
                resp = await cleanup_client.get(
                    f"{BASE}/admin/users",
                    params={"keyword": phone},
                    headers=_headers(tok),
                )
                if resp.status_code == 200:
                    items = resp.json()["data"]["items"]
                    uid = next((u["id"] for u in items if u["phone"] == phone), None)
                    if uid:
                        await cleanup_client.delete(
                            f"{BASE}/admin/users/{uid}", headers=_headers(tok)
                        )
            except Exception:
                pass


@pytest.mark.asyncio
class TestBookingOwnership:
    """F2.2 预约数据归属与泄露修复"""

    async def test_student_list_only_own(self, client: AsyncClient, booking_data):
        """AC-3：学员 A GET /bookings 只返回自己的预约"""
        token = await _login(client, SEED_STUDENT_A)
        resp = await client.get(f"{BASE}/bookings", headers=_headers(token))
        assert resp.status_code == 200, resp.text
        items = resp.json()["data"]["items"]
        assert items, "学员 A 应至少有 1 条预约"
        a_id = booking_data["a_id"]
        for it in items:
            assert it["student_id"] == a_id, f"学员列表出现他人预约: {it['student_id']}"

    async def test_student_query_by_schedule_only_own(
        self, client: AsyncClient, booking_data
    ):
        """AC-1：学员 B 按 schedule_id 查 schedule_T，不应看到 A 的预约"""
        token_b = await _login(
            client, {"phone": booking_data["b_phone"], "password": "Test@123456"}
        )
        resp = await client.get(
            f"{BASE}/bookings",
            params={"schedule_id": booking_data["schedule_t_id"]},
            headers=_headers(token_b),
        )
        assert resp.status_code == 200, resp.text
        items = resp.json()["data"]["items"]
        # B 在 schedule_T 有预约，A 也有——B 只能看到自己的
        for it in items:
            assert it["student_id"] == booking_data["b_id"], "学员 B 看到他人预约（越权）"

        # 对照：A 查同一 schedule 能看到自己在该排期的预约
        token_a = await _login(client, SEED_STUDENT_A)
        resp_a = await client.get(
            f"{BASE}/bookings",
            params={"schedule_id": booking_data["schedule_t_id"]},
            headers=_headers(token_a),
        )
        assert resp_a.status_code == 200
        items_a = resp_a.json()["data"]["items"]
        assert any(it["id"] == booking_data["booking_a_on_t_id"] for it in items_a)
        assert all(it["student_id"] == booking_data["a_id"] for it in items_a)

    async def test_student_get_others_booking_forbidden(
        self, client: AsyncClient, booking_data
    ):
        """AC-2：学员 A 查 B 的预约详情 → 403"""
        token = await _login(client, SEED_STUDENT_A)
        resp = await client.get(
            f"{BASE}/bookings/{booking_data['booking_b_on_t_id']}",
            headers=_headers(token),
        )
        assert resp.status_code == 403, f"查他人预约应 403，实际 {resp.status_code}: {resp.text}"
        assert "无权" in resp.json()["msg"]

    async def test_student_get_own_booking_ok(self, client: AsyncClient, booking_data):
        """AC-10：学员 A 查自己的预约 → 200"""
        token = await _login(client, SEED_STUDENT_A)
        resp = await client.get(
            f"{BASE}/bookings/{booking_data['booking_a_on_t_id']}",
            headers=_headers(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["id"] == booking_data["booking_a_on_t_id"]

    async def test_get_nonexistent_returns_404(self, client: AsyncClient, booking_data):
        """AC-11：不存在的预约 → 404"""
        token = await _login(client, SEED_STUDENT_A)
        resp = await client.get(f"{BASE}/bookings/999999999", headers=_headers(token))
        assert resp.status_code == 404
        assert "不存在" in resp.json()["msg"]

    async def test_teacher_list_only_own_schedules(self, client: AsyncClient, booking_data):
        """AC-4：教师 T GET /bookings 只返回 schedule_T 下的预约（不含 schedule_T2）"""
        token = await _login(client, SEED_TEACHER_T)
        resp = await client.get(f"{BASE}/bookings", headers=_headers(token))
        assert resp.status_code == 200, resp.text
        items = resp.json()["data"]["items"]
        assert items, "教师 T 应看到其排期下的预约"
        schedule_t2_id = booking_data["schedule_t2_id"]
        for it in items:
            assert it["schedule_id"] != schedule_t2_id, "教师看到他人排期的预约（越权）"
        # 应包含 A 与 B 在 schedule_T 的预约
        ids = {it["id"] for it in items}
        assert booking_data["booking_a_on_t_id"] in ids
        assert booking_data["booking_b_on_t_id"] in ids
        assert booking_data["booking_a_on_t2_id"] not in ids

    async def test_teacher_get_own_schedule_booking_ok(
        self, client: AsyncClient, booking_data
    ):
        """AC-5a：教师 T 查其排期下的预约（A 在 schedule_T）→ 200"""
        token = await _login(client, SEED_TEACHER_T)
        resp = await client.get(
            f"{BASE}/bookings/{booking_data['booking_a_on_t_id']}",
            headers=_headers(token),
        )
        assert resp.status_code == 200, resp.text

    async def test_teacher_get_other_schedule_booking_forbidden(
        self, client: AsyncClient, booking_data
    ):
        """AC-5b：教师 T 查 T2 排期下的预约（A 在 schedule_T2）→ 403"""
        token = await _login(client, SEED_TEACHER_T)
        resp = await client.get(
            f"{BASE}/bookings/{booking_data['booking_a_on_t2_id']}",
            headers=_headers(token),
        )
        assert resp.status_code == 403, f"查他人排期预约应 403，实际 {resp.status_code}"

    async def test_admin_full_access(self, client: AsyncClient, admin_token, booking_data):
        """AC-6：super_admin 可查列表与任意详情"""
        resp = await client.get(f"{BASE}/bookings", headers=_headers(admin_token))
        assert resp.status_code == 200, resp.text
        items = resp.json()["data"]["items"]
        ids = {it["id"] for it in items}
        assert booking_data["booking_a_on_t_id"] in ids
        assert booking_data["booking_b_on_t_id"] in ids
        assert booking_data["booking_a_on_t2_id"] in ids

        # 任意详情
        for bid in (
            booking_data["booking_a_on_t_id"],
            booking_data["booking_b_on_t_id"],
            booking_data["booking_a_on_t2_id"],
        ):
            r = await client.get(f"{BASE}/bookings/{bid}", headers=_headers(admin_token))
            assert r.status_code == 200, f"admin 查 {bid} 应 200，实际 {r.status_code}"

    async def test_service_level_student_path_like_mcp(
        self, booking_data
    ):
        """AC-8：直调 Service（MCP get_my_bookings 等价路径），student 用户只返回自己

        MCP get_my_bookings 以 current_user={"user_id","tenant_id"} 调 list_bookings，
        与 HTTP 学员路径走同一归属分流。
        """
        settings = get_settings()
        engine = create_async_engine(
            settings.DATABASE_URL, echo=False, pool_size=2, max_overflow=3, pool_pre_ping=True
        )
        session_factory = async_sessionmaker(
            bind=engine, class_=AsyncSession, expire_on_commit=False
        )
        try:
            async with session_factory() as db:
                set_tenant_id(booking_data["tenant_id"])
                service = BookingService()
                result = await service.list_bookings(
                    db,
                    current_user={
                        "user_id": booking_data["a_id"],
                        "tenant_id": booking_data["tenant_id"],
                    },
                    page=1,
                    page_size=50,
                )
                assert result.items, "学员 A 应有预约"
                for it in result.items:
                    assert it.student_id == booking_data["a_id"], "Service 返回他人预约"
                # 不含 A 在 T2 的预约也应是 A 自己的（student 分支只按 student_id 过滤，
                # 实际会包含 A 在 schedule_T2 的预约，因为那也是 A 自己的）
                ids = {it.id for it in result.items}
                assert booking_data["booking_a_on_t2_id"] in ids
        finally:
            await engine.dispose()
