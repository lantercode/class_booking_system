"""存量排期延迟任务补投测试（灰度上线补偿）。

覆盖：
- 启用 Worker 后为存量 NORMAL 排期补投「自动完成 + 人数不足取消」；
- 重复执行不产生新任务，也不会把已完成（done）的任务重置为 pending；
- 非 NORMAL 排期不投递；
- ``TASK_WORKER_ENABLED=false`` 时直接返回，不写库。
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from app.modules.course.models import CourseType
from app.modules.schedule.jobs import (
    backfill_schedule_jobs,
    finish_job_key,
    underbooked_job_key,
)
from app.modules.schedule.models import CourseSchedule, ScheduleStatus
from tests.membership_support import (
    create_course,
    create_schedule,
    db_factory,
    get_seed_ids,
)

JOBS_MODULE = "app.modules.schedule.jobs"


def _settings(*, worker: bool = True):
    return SimpleNamespace(
        TASK_WORKER_ENABLED=worker,
        AUTO_FINISH_ENABLED=True,
        AUTO_FINISH_GRACE_MINUTES=30,
        AUTO_CANCEL_UNDERBOOKED_ENABLED=True,
    )


@pytest.fixture(scope="function")
async def env():
    async with db_factory() as factory:
        ids = await get_seed_ids(factory)
        created = {"course_ids": [], "schedule_ids": [], "type_codes": []}
        yield factory, ids, created
        async with factory() as session:
            await session.execute(
                text("DELETE FROM job_queue WHERE tenant_id = :tid"),
                {"tid": ids["tenant_id"]},
            )
            for sid in created["schedule_ids"]:
                await session.execute(
                    text("DELETE FROM course_schedules WHERE id = :i"), {"i": sid}
                )
            for cid in created["course_ids"]:
                await session.execute(text("DELETE FROM courses WHERE id = :i"), {"i": cid})
            for code in created["type_codes"]:
                await session.execute(
                    text("DELETE FROM course_types WHERE code = :c"), {"c": code}
                )
            await session.commit()


async def _make_course_type(factory, tenant_id: int):
    code = f"bf-{uuid4().hex[:8]}"
    async with factory() as session:
        session.add(
            CourseType(
                tenant_id=tenant_id,
                name="补投测试类型",
                code=code,
                min_students=3,
                cancel_before_minutes=60,
            )
        )
        await session.commit()
    return code


async def _job_rows(factory, tenant_id: int, key: str) -> list[dict]:
    async with factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT status, run_at FROM job_queue "
                    "WHERE tenant_id = :tid AND idempotency_key = :k"
                ),
                {"tid": tenant_id, "k": key},
            )
        ).mappings().all()
    return [dict(row) for row in rows]


@pytest.mark.asyncio
async def test_backfill_enqueues_and_is_idempotent(env):
    factory, ids, created = env
    tenant_id = ids["tenant_id"]
    code = await _make_course_type(factory, tenant_id)
    created["type_codes"].append(code)
    course_id = await create_course(factory, tenant_id, course_type_code=code)
    created["course_ids"].append(course_id)
    start_at = datetime.now(UTC) + timedelta(days=2)
    schedule_id = await create_schedule(
        factory,
        tenant_id,
        course_id=course_id,
        teacher_id=ids["teacher_id"],
        start_at=start_at,
    )
    created["schedule_ids"].append(schedule_id)

    with (
        patch(f"{JOBS_MODULE}.get_settings", lambda: _settings()),
        patch(
            f"{JOBS_MODULE}._active_tenant_ids",
            new=AsyncMock(return_value=[tenant_id]),
        ),
    ):
        first = await backfill_schedule_jobs()
        second = await backfill_schedule_jobs()

    assert first["enqueued"] >= 2
    assert second["enqueued"] == 0

    finish = await _job_rows(factory, tenant_id, finish_job_key(schedule_id))
    underbooked = await _job_rows(factory, tenant_id, underbooked_job_key(schedule_id))
    assert len(finish) == 1 and finish[0]["status"] == "pending"
    assert len(underbooked) == 1 and underbooked[0]["status"] == "pending"
    assert abs(
        (finish[0]["run_at"] - (start_at + timedelta(minutes=90))).total_seconds()
    ) < 5


@pytest.mark.asyncio
async def test_backfill_does_not_reset_done_job(env):
    factory, ids, created = env
    tenant_id = ids["tenant_id"]
    code = await _make_course_type(factory, tenant_id)
    created["type_codes"].append(code)
    course_id = await create_course(factory, tenant_id, course_type_code=code)
    created["course_ids"].append(course_id)
    schedule_id = await create_schedule(
        factory,
        tenant_id,
        course_id=course_id,
        teacher_id=ids["teacher_id"],
        start_at=datetime.now(UTC) + timedelta(days=1),
    )
    created["schedule_ids"].append(schedule_id)

    async with factory() as session:
        await session.execute(
            text(
                """
                INSERT INTO job_queue
                    (tenant_id, type, idempotency_key, payload, run_at, status)
                VALUES
                    (:tid, 'finish_schedule', :key, '{}'::jsonb, now(), 'done')
                """
            ).bindparams(tid=tenant_id, key=finish_job_key(schedule_id))
        )
        await session.commit()

    with (
        patch(f"{JOBS_MODULE}.get_settings", lambda: _settings()),
        patch(
            f"{JOBS_MODULE}._active_tenant_ids",
            new=AsyncMock(return_value=[tenant_id]),
        ),
    ):
        await backfill_schedule_jobs()

    finish = await _job_rows(factory, tenant_id, finish_job_key(schedule_id))
    assert len(finish) == 1
    assert finish[0]["status"] == "done"


@pytest.mark.asyncio
async def test_backfill_skips_non_normal_schedule(env):
    factory, ids, created = env
    tenant_id = ids["tenant_id"]
    course_id = await create_course(factory, tenant_id, course_type_code=None)
    created["course_ids"].append(course_id)
    schedule_id = await create_schedule(
        factory,
        tenant_id,
        course_id=course_id,
        teacher_id=ids["teacher_id"],
        start_at=datetime.now(UTC) + timedelta(days=1),
    )
    created["schedule_ids"].append(schedule_id)

    async with factory() as session:
        schedule = (
            await session.execute(
                select(CourseSchedule).where(CourseSchedule.id == schedule_id)
            )
        ).scalars().one()
        schedule.status = ScheduleStatus.CANCELLED.value
        await session.commit()

    with (
        patch(f"{JOBS_MODULE}.get_settings", lambda: _settings()),
        patch(
            f"{JOBS_MODULE}._active_tenant_ids",
            new=AsyncMock(return_value=[tenant_id]),
        ),
    ):
        await backfill_schedule_jobs()

    assert await _job_rows(factory, tenant_id, finish_job_key(schedule_id)) == []
    assert await _job_rows(factory, tenant_id, underbooked_job_key(schedule_id)) == []


@pytest.mark.asyncio
async def test_backfill_noop_when_worker_disabled(env):
    factory, ids, created = env
    tenant_id = ids["tenant_id"]
    course_id = await create_course(factory, tenant_id, course_type_code=None)
    created["course_ids"].append(course_id)
    schedule_id = await create_schedule(
        factory,
        tenant_id,
        course_id=course_id,
        teacher_id=ids["teacher_id"],
        start_at=datetime.now(UTC) + timedelta(days=1),
    )
    created["schedule_ids"].append(schedule_id)

    with patch(
        f"{JOBS_MODULE}.get_settings", lambda: _settings(worker=False)
    ):
        stats = await backfill_schedule_jobs()

    assert stats == {"tenants": 0, "schedules": 0, "enqueued": 0}
    assert await _job_rows(factory, tenant_id, finish_job_key(schedule_id)) == []
