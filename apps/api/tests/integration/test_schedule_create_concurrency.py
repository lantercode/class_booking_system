"""
F4.5 排期创建并发安全 - 集成测试

验证目标（对应 Feature 4.5 Acceptance Criteria）：
- AC-1：并发创建两个时间重叠（同教师）的排期，有且仅有一个成功，
        另一个收到冲突业务错误（BusinessException 400），DB 中只落 1 行。
- AC-2：并发创建两个时间不重叠（同教师）的排期，两者均成功，DB 落 2 行。
- AC-3：SerializationFailure（SQLSTATE 40001）被 Service 捕获并重试，
        重试后以新快照重跑冲突检查并成功落库。
- AC-4：序列化失败持续发生、重试耗尽后，返回友好业务错误（非 traceback 透传）。
- AC-5：回归：既有 F4.4 / F4.1 / F4.2 测试不受影响（在 runtime-test-report 中执行）。

并发模型：
  - 两个独立 AsyncSession（同一 session_factory，不同连接 → 两个真实 DB 事务），
    asyncio.gather 并发执行 Service.create_schedule。
  - 使用真实 asyncpg + 真实 PostgreSQL（默认 READ COMMITTED，本特性将创建事务
    显式提升为 SERIALIZABLE）。

测试数据标记：capacity=78 + 时间窗口位于 2099 年，避免与存量数据冲突；
每个用例 finally 自行清理创建的排期。

前置条件：
  - migration f44ab1c2d3e4 已 apply
  - 种子数据已由 conftest.seed_test_database 初始化（teacher=13800138001）

运行方式：
    cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest \
        tests/integration/test_schedule_create_concurrency.py -v
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.exceptions import BusinessException
from app.core.tenant_context import set_tenant_id
from app.modules.course.models import Course
from app.modules.schedule.models import CourseSchedule, ScheduleStatus
from app.modules.schedule.repository import ScheduleRepository
from app.modules.schedule.schemas import ScheduleCreate
from app.modules.schedule.service import ScheduleService
from app.modules.tenant.models import Tenant
from app.modules.user.models import User

TENANT_SLUG = "dance-school"
SEED_TEACHER_PHONE = "13800138001"

# 测试标记：容量 78 + 2099 年时间窗，便于清理与隔离
TEST_CAPACITY = 78
BASE_DAY = datetime(2099, 6, 1, 10, 0, tzinfo=UTC)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture(scope="session")
async def shared_data():
    """session-scoped：解析种子 tenant/teacher + 任一既有 course_id，返回纯数据 dict。"""
    settings = get_settings()
    engine = create_async_engine(
        settings.DATABASE_URL, echo=False, pool_size=3, max_overflow=5, pool_pre_ping=True
    )
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        tenant_id = (
            await session.execute(select(Tenant).where(Tenant.slug == TENANT_SLUG))
        ).scalar_one().id
        teacher_id = (
            await session.execute(select(User).where(User.phone == SEED_TEACHER_PHONE))
        ).scalar_one().id
        course_id = (
            await session.execute(
                select(Course.id).where(Course.tenant_id == tenant_id).limit(1)
            )
        ).scalar_one()

    data = {"tenant_id": tenant_id, "teacher_id": teacher_id, "course_id": course_id}
    yield data

    # 兜底清理：capacity=78 的测试排期
    async with session_factory() as session:
        set_tenant_id(data["tenant_id"])
        await session.execute(
            delete(CourseSchedule).where(
                CourseSchedule.tenant_id == data["tenant_id"],
                CourseSchedule.capacity == TEST_CAPACITY,
            )
        )
        await session.commit()
    await engine.dispose()


@pytest.fixture(scope="function")
async def sf():
    """function-scoped engine + session_factory（pool≥2，支撑双事务并发）。"""
    settings = get_settings()
    engine = create_async_engine(
        settings.DATABASE_URL, echo=False, pool_size=4, max_overflow=4, pool_pre_ping=True
    )
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    yield session_factory
    await engine.dispose()


# ============================================================
# Helpers
# ============================================================


async def _create_via_service(sf, data: dict, start: datetime, end: datetime):
    """独立 session + 独立事务调用 Service.create_schedule（模拟一个并发请求）。"""
    async with sf() as session:
        set_tenant_id(data["tenant_id"])
        payload = ScheduleCreate(
            course_id=data["course_id"],
            teacher_id=data["teacher_id"],
            classroom_id=None,
            start_at=start,
            end_at=end,
            capacity=TEST_CAPACITY,
        )
        return await ScheduleService().create_schedule(session, payload)


async def _count_window(sf, data: dict, start: datetime, end: datetime) -> int:
    """统计指定时间窗口内 NORMAL 状态的测试排期数。"""
    async with sf() as session:
        set_tenant_id(data["tenant_id"])
        result = await session.execute(
            select(func.count())
            .select_from(CourseSchedule)
            .where(
                CourseSchedule.tenant_id == data["tenant_id"],
                CourseSchedule.capacity == TEST_CAPACITY,
                CourseSchedule.status == ScheduleStatus.NORMAL.value,
                CourseSchedule.start_at < end,
                CourseSchedule.end_at > start,
            )
        )
        return result.scalar() or 0


async def _cleanup(sf, data: dict) -> None:
    async with sf() as session:
        set_tenant_id(data["tenant_id"])
        await session.execute(
            delete(CourseSchedule).where(
                CourseSchedule.tenant_id == data["tenant_id"],
                CourseSchedule.capacity == TEST_CAPACITY,
            )
        )
        await session.commit()


# ============================================================
# 测试用例
# ============================================================


class TestConcurrentCreateConflict:
    """AC-1：并发创建时间重叠排期 → 仅一个成功"""

    async def test_concurrent_overlapping_only_one_succeeds(self, shared_data, sf):
        start = BASE_DAY
        end = BASE_DAY + timedelta(hours=1)
        try:
            results = await asyncio.gather(
                _create_via_service(sf, shared_data, start, end),
                _create_via_service(sf, shared_data, start, end),
                return_exceptions=True,
            )

            successes = [r for r in results if not isinstance(r, BaseException)]
            failures = [r for r in results if isinstance(r, BaseException)]

            assert len(successes) == 1, (
                f"并发重叠创建必须恰好一个成功，实际成功 {len(successes)} 个: {results}"
            )
            assert len(failures) == 1
            # 失败方必须是冲突业务错误（400），不允许 traceback 类异常透传
            assert isinstance(failures[0], BusinessException)
            assert failures[0].code == 400

            # DB 层面该时间窗内只有 1 行落库
            assert await _count_window(sf, shared_data, start, end) == 1
        finally:
            await _cleanup(sf, shared_data)

    async def test_concurrent_partial_overlap_only_one_succeeds(self, shared_data, sf):
        """部分重叠（30 分钟交叠）同样被判定冲突。"""
        start1 = BASE_DAY + timedelta(hours=2)
        end1 = start1 + timedelta(hours=1)
        start2 = start1 + timedelta(minutes=30)
        end2 = start2 + timedelta(hours=1)
        try:
            results = await asyncio.gather(
                _create_via_service(sf, shared_data, start1, end1),
                _create_via_service(sf, shared_data, start2, end2),
                return_exceptions=True,
            )
            successes = [r for r in results if not isinstance(r, BaseException)]
            failures = [r for r in results if isinstance(r, BaseException)]
            assert len(successes) == 1
            assert len(failures) == 1
            assert isinstance(failures[0], BusinessException)
        finally:
            await _cleanup(sf, shared_data)


class TestConcurrentCreateNonOverlapping:
    """AC-2：并发创建时间不重排档期 → 均成功"""

    async def test_concurrent_non_overlapping_both_succeed(self, shared_data, sf):
        start1 = BASE_DAY + timedelta(hours=4)
        end1 = start1 + timedelta(hours=1)
        start2 = BASE_DAY + timedelta(hours=6)
        end2 = start2 + timedelta(hours=1)
        try:
            results = await asyncio.gather(
                _create_via_service(sf, shared_data, start1, end1),
                _create_via_service(sf, shared_data, start2, end2),
                return_exceptions=True,
            )
            successes = [r for r in results if not isinstance(r, BaseException)]
            failures = [r for r in results if isinstance(r, BaseException)]

            assert len(failures) == 0, f"非重叠并发创建不应失败: {failures}"
            assert len(successes) == 2
            assert successes[0].id != successes[1].id

            # 两个窗口各落 1 行
            assert await _count_window(sf, shared_data, start1, end1) == 1
            assert await _count_window(sf, shared_data, start2, end2) == 1
        finally:
            await _cleanup(sf, shared_data)


class TestSerializationFailureHandling:
    """AC-3/AC-4：SerializationFailure 重试与耗尽兜底"""

    async def test_serialization_failure_retried_and_succeeds(
        self, shared_data, sf, monkeypatch
    ):
        """注入一次性 40001 → Service 重试后成功落库（AC-3）。"""
        import asyncpg

        attempts = {"count": 0}
        original_find_conflicts = ScheduleRepository.find_conflicts

        async def flaky_find_conflicts(self, db, **kwargs):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise asyncpg.exceptions.SerializationError(
                    "could not serialize access due to read/write dependencies "
                    "among transactions"
                )
            return await original_find_conflicts(self, db, **kwargs)

        monkeypatch.setattr(ScheduleRepository, "find_conflicts", flaky_find_conflicts)

        start = BASE_DAY + timedelta(hours=8)
        end = start + timedelta(hours=1)
        try:
            async with sf() as session:
                set_tenant_id(shared_data["tenant_id"])
                payload = ScheduleCreate(
                    course_id=shared_data["course_id"],
                    teacher_id=shared_data["teacher_id"],
                    classroom_id=None,
                    start_at=start,
                    end_at=end,
                    capacity=TEST_CAPACITY,
                )
                result = await ScheduleService().create_schedule(session, payload)

            assert result.id is not None
            assert attempts["count"] == 2, (
                f"第一次应注入失败、第二次成功，实际调用 {attempts['count']} 次"
            )
            assert await _count_window(sf, shared_data, start, end) == 1
        finally:
            await _cleanup(sf, shared_data)

    async def test_serialization_failure_exhausted_returns_business_error(
        self, shared_data, sf, monkeypatch
    ):
        """持续 40001 → 重试耗尽 → 友好 BusinessException，不透传 traceback（AC-4）。"""
        import asyncpg

        attempts = {"count": 0}

        async def always_fail_find_conflicts(self, db, **kwargs):
            attempts["count"] += 1
            raise asyncpg.exceptions.SerializationError(
                "could not serialize access due to read/write dependencies "
                "among transactions"
            )

        monkeypatch.setattr(
            ScheduleRepository, "find_conflicts", always_fail_find_conflicts
        )

        start = BASE_DAY + timedelta(hours=10)
        end = start + timedelta(hours=1)
        try:
            async with sf() as session:
                set_tenant_id(shared_data["tenant_id"])
                payload = ScheduleCreate(
                    course_id=shared_data["course_id"],
                    teacher_id=shared_data["teacher_id"],
                    classroom_id=None,
                    start_at=start,
                    end_at=end,
                    capacity=TEST_CAPACITY,
                )
                with pytest.raises(BusinessException) as exc_info:
                    await ScheduleService().create_schedule(session, payload)

            assert "重试" in exc_info.value.msg
            # 首次 + 2 次重试 = 3 次尝试
            assert attempts["count"] == 3, (
                f"应尝试 3 次后放弃，实际 {attempts['count']} 次"
            )
            # 未落库任何行
            assert await _count_window(sf, shared_data, start, end) == 0
        finally:
            await _cleanup(sf, shared_data)


class TestSerialBehaviorUnchanged:
    """串行路径行为不变：冲突检测、合法创建与参数校验"""

    async def test_serial_conflict_still_rejected(self, shared_data, sf):
        """串行创建重叠排期，第二个必须收到冲突业务错误。"""
        start = BASE_DAY + timedelta(hours=12)
        end = start + timedelta(hours=1)
        try:
            first = await _create_via_service(sf, shared_data, start, end)
            assert first.id is not None

            with pytest.raises(BusinessException) as exc_info:
                await _create_via_service(sf, shared_data, start, end)
            assert exc_info.value.code == 400
            assert "教师时间冲突" in exc_info.value.msg

            assert await _count_window(sf, shared_data, start, end) == 1
        finally:
            await _cleanup(sf, shared_data)

    async def test_serial_valid_create_succeeds(self, shared_data, sf):
        """单个合法创建成功且字段正确。"""
        start = BASE_DAY + timedelta(hours=14)
        end = start + timedelta(hours=1)
        try:
            result = await _create_via_service(sf, shared_data, start, end)
            assert result.id is not None
            assert result.teacher_id == shared_data["teacher_id"]
            assert result.status == ScheduleStatus.NORMAL.value
            assert result.booked_count == 0
        finally:
            await _cleanup(sf, shared_data)

    async def test_invalid_time_range_rejected(self, shared_data, sf):
        """end <= start 仍在事务外被 ValidationException 拦截。"""
        from app.core.exceptions import ValidationException

        start = BASE_DAY + timedelta(hours=16)
        async with sf() as session:
            set_tenant_id(shared_data["tenant_id"])
            payload = ScheduleCreate(
                course_id=shared_data["course_id"],
                teacher_id=shared_data["teacher_id"],
                classroom_id=None,
                start_at=start,
                end_at=start,  # end == start，非法
                capacity=TEST_CAPACITY,
            )
            with pytest.raises(ValidationException):
                await ScheduleService().create_schedule(session, payload)


class TestLockedConflictRowNotSkipped:
    """数据库评审回归：被并发 RC 事务持行锁的"已存在冲突行"不得被 SKIP LOCKED 吞掉。

    场景（F4.5 评审 NEEDS_FIX 项）：
      1. 已存在一条 NORMAL 排期 S（已提交）；
      2. 另一个 READ COMMITTED 事务（模拟预约/取消链路的
         increment/decrement_booked_count）以 SELECT ... FOR UPDATE 持有 S
         的行锁，尚未提交；
      3. 此刻创建与 S 时间重叠的排期：
         - use_lock=True（旧实现）→ FOR UPDATE SKIP LOCKED 跳过被锁的 S →
           误判无冲突 → 静默双占，且锁方为 RC 不产生 SIREAD 锁，40001 无法兜底；
         - use_lock=False（修复后）→ SERIALIZABLE 普通快照谓词读仍可见 S →
           冲突业务错误 400，不产生第二行。
    """

    async def test_existing_conflict_row_locked_by_rc_tx_is_still_detected(
        self, shared_data, sf
    ):
        start = BASE_DAY + timedelta(hours=18)
        end = start + timedelta(hours=1)
        try:
            # 1) 先正常创建已存在的冲突排期 S
            existing = await _create_via_service(sf, shared_data, start, end)
            assert existing.id is not None

            # 2) RC 事务持有 S 的行锁但不提交（async with 退出时才 rollback 释放）
            async with sf() as lock_session:
                set_tenant_id(shared_data["tenant_id"])
                locked_rows = (
                    await lock_session.execute(
                        select(CourseSchedule)
                        .where(CourseSchedule.id == existing.id)
                        .with_for_update()
                    )
                ).scalars().all()
                assert len(locked_rows) == 1, "前置条件：必须成功持有 S 的行锁"

                # 3a) 直接复现根因：SKIP LOCKED 在持锁窗口内会把 S 吞掉
                async with sf() as probe_session:
                    set_tenant_id(shared_data["tenant_id"])
                    repo = ScheduleRepository()
                    swallowed = await repo.find_conflicts(
                        probe_session,
                        teacher_id=shared_data["teacher_id"],
                        start_at=start,
                        end_at=end,
                        use_lock=True,
                    )
                    assert swallowed["has_conflict"] is False, (
                        "SKIP LOCKED 必须跳过被持锁行（本断言用于固化漏判根因）"
                    )

                    # 3b) 同一窗口普通快照读必须看到 S
                    visible = await repo.find_conflicts(
                        probe_session,
                        teacher_id=shared_data["teacher_id"],
                        start_at=start,
                        end_at=end,
                        use_lock=False,
                    )
                    assert visible["has_conflict"] is True
                    assert len(visible["teacher_conflicts"]) == 1
                    assert visible["teacher_conflicts"][0].id == existing.id

                # 3c) 修复后 Service 路径必须拒绝重叠创建（400，非双写）
                with pytest.raises(BusinessException) as exc_info:
                    await _create_via_service(sf, shared_data, start, end)
                assert exc_info.value.code == 400
                assert "教师时间冲突" in exc_info.value.msg

                # DB 中仍只有 S 一行，锁方提交/回滚都不应改变该结论
                assert await _count_window(sf, shared_data, start, end) == 1
        finally:
            await _cleanup(sf, shared_data)
