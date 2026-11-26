"""阶段 3 排期延迟任务迁移测试。

覆盖：
- ``sync_schedule_jobs`` 投递「自动完成 + 人数不足取消」两个延迟任务，并可按变更覆盖 run_at；
- ``finish_schedule`` handler 到点收口排期；
- ``cancel_schedule_if_underbooked`` handler：到点人数不足取消 / 未到点重投递。
"""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from app.modules.course.models import CourseType
from app.modules.schedule.jobs import sync_schedule_jobs
from app.modules.schedule.models import CourseSchedule, ScheduleStatus
from app.modules.task.service import (
    cancel_schedule_if_underbooked,
    finish_schedule,
)
from tests.membership_support import (
    create_course,
    create_schedule,
    db_factory,
    get_seed_ids,
)


def _job_settings(
    *, finish_enabled: bool = True, cancel_enabled: bool = True, grace: int = 30
):
    return SimpleNamespace(
        AUTO_FINISH_ENABLED=finish_enabled,
        AUTO_FINISH_GRACE_MINUTES=grace,
        AUTO_CANCEL_UNDERBOOKED_ENABLED=cancel_enabled,
    )


@pytest.fixture(scope="function")
async def env():
    async with db_factory() as factory:
        ids = await get_seed_ids(factory)
        created = {"course_ids": [], "schedule_ids": [], "type_codes": []}
        yield factory, ids, created
        # 清理：job → schedule → course → course_type
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


async def _make_course_type(factory, tenant_id: int, *, min_students=3, cancel_before=60):
    code = f"t3-{uuid4().hex[:8]}"
    async with factory() as session:
        session.add(
            CourseType(
                tenant_id=tenant_id,
                name="阶段3测试类型",
                code=code,
                min_students=min_students,
                cancel_before_minutes=cancel_before,
            )
        )
        await session.commit()
    return code


async def _load_schedule(factory, schedule_id: int) -> CourseSchedule:
    async with factory() as session:
        return (
            await session.execute(
                select(CourseSchedule).where(CourseSchedule.id == schedule_id)
            )
        ).scalars().one()


async def _jobs(factory, tenant_id: int) -> dict[str, dict]:
    async with factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT type, run_at, status, payload FROM job_queue "
                    "WHERE tenant_id = :tid"
                ),
                {"tid": tenant_id},
            )
        ).mappings().all()
    out = {}
    for row in rows:
        payload = row["payload"]
        out[row["type"]] = {
            "run_at": row["run_at"],
            "status": row["status"],
            "payload": json.loads(payload) if isinstance(payload, str) else payload,
        }
    return out


@pytest.mark.asyncio
async def test_sync_creates_finish_and_underbooked_jobs(env):
    factory, ids, created = env
    code = await _make_course_type(factory, ids["tenant_id"])
    created["type_codes"].append(code)
    course_id = await create_course(
        factory, ids["tenant_id"], course_type_code=code
    )
    created["course_ids"].append(course_id)
    start_at = datetime.now(UTC) + timedelta(days=2)
    schedule_id = await create_schedule(
        factory, ids["tenant_id"],
        course_id=course_id, teacher_id=ids["teacher_id"], start_at=start_at,
    )
    created["schedule_ids"].append(schedule_id)

    schedule = await _load_schedule(factory, schedule_id)
    with patch("app.modules.schedule.jobs.get_settings", lambda: _job_settings()):
        async with factory() as db:
            await sync_schedule_jobs(db, schedule)
            await db.commit()

    jobs = await _jobs(factory, ids["tenant_id"])
    assert set(jobs) == {"finish_schedule", "cancel_schedule_if_underbooked"}
    # 自动完成 = end_at(开始+1h) + 30min grace
    assert abs(
        (jobs["finish_schedule"]["run_at"] - (start_at + timedelta(minutes=90))).total_seconds()
    ) < 5
    # 人数不足取消 = start_at - 60min
    assert abs(
        (jobs["cancel_schedule_if_underbooked"]["run_at"] - (start_at - timedelta(minutes=60))).total_seconds()
    ) < 5
    assert jobs["cancel_schedule_if_underbooked"]["payload"]["min_students"] == 3


@pytest.mark.asyncio
async def test_sync_overwrites_run_at_when_schedule_changed(env):
    factory, ids, created = env
    code = await _make_course_type(factory, ids["tenant_id"])
    created["type_codes"].append(code)
    course_id = await create_course(factory, ids["tenant_id"], course_type_code=code)
    created["course_ids"].append(course_id)
    start_at = datetime.now(UTC) + timedelta(days=2)
    schedule_id = await create_schedule(
        factory, ids["tenant_id"],
        course_id=course_id, teacher_id=ids["teacher_id"], start_at=start_at,
    )
    created["schedule_ids"].append(schedule_id)

    with patch("app.modules.schedule.jobs.get_settings", lambda: _job_settings()):
        async with factory() as db:
            await sync_schedule_jobs(db, await _load_schedule(factory, schedule_id))
            await db.commit()

        # 模拟排期改期：整体后移 3 天
        async with factory() as db:
            schedule = (
                await db.execute(
                    select(CourseSchedule).where(CourseSchedule.id == schedule_id)
                )
            ).scalars().one()
            schedule.start_at = start_at + timedelta(days=3)
            schedule.end_at = schedule.start_at + timedelta(hours=1)
            await db.commit()
            await sync_schedule_jobs(db, schedule)
            await db.commit()

    jobs = await _jobs(factory, ids["tenant_id"])
    # 唯一键保证每种任务只有一条，且 run_at 已覆盖为新时间
    assert len(jobs) == 2
    assert abs(
        (jobs["finish_schedule"]["run_at"] - (start_at + timedelta(days=3, minutes=90))).total_seconds()
    ) < 5


@pytest.mark.asyncio
async def test_finish_schedule_handler_finalizes(env):
    factory, ids, created = env
    course_id = await create_course(factory, ids["tenant_id"], course_type_code=None)
    created["course_ids"].append(course_id)
    schedule_id = await create_schedule(
        factory, ids["tenant_id"],
        course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=datetime.now(UTC) - timedelta(hours=3),
    )
    created["schedule_ids"].append(schedule_id)

    async with factory() as db:
        await finish_schedule(db, {"schedule_id": schedule_id}, tenant_id=ids["tenant_id"])
        await db.commit()

    assert (await _load_schedule(factory, schedule_id)).status == ScheduleStatus.FINISHED.value


@pytest.mark.asyncio
async def test_underbooked_handler_cancels_after_deadline(env):
    factory, ids, created = env
    code = await _make_course_type(factory, ids["tenant_id"], min_students=3, cancel_before=60)
    created["type_codes"].append(code)
    course_id = await create_course(factory, ids["tenant_id"], course_type_code=code)
    created["course_ids"].append(course_id)
    # 距开始 10 分钟，已过「开课前 60 分钟」截止点
    schedule_id = await create_schedule(
        factory, ids["tenant_id"],
        course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    created["schedule_ids"].append(schedule_id)

    async with factory() as db:
        await cancel_schedule_if_underbooked(
            db, {"schedule_id": schedule_id, "min_students": 3}, tenant_id=ids["tenant_id"]
        )
        await db.commit()

    assert (await _load_schedule(factory, schedule_id)).status == (
        ScheduleStatus.CANCELLED.value
    )


@pytest.mark.asyncio
async def test_underbooked_handler_reschedules_before_deadline(env):
    factory, ids, created = env
    code = await _make_course_type(factory, ids["tenant_id"], min_students=3, cancel_before=60)
    created["type_codes"].append(code)
    course_id = await create_course(factory, ids["tenant_id"], course_type_code=code)
    created["course_ids"].append(course_id)
    start_at = datetime.now(UTC) + timedelta(days=1)
    schedule_id = await create_schedule(
        factory, ids["tenant_id"],
        course_id=course_id, teacher_id=ids["teacher_id"], start_at=start_at,
    )
    created["schedule_ids"].append(schedule_id)

    async with factory() as db:
        await cancel_schedule_if_underbooked(
            db, {"schedule_id": schedule_id, "min_students": 3}, tenant_id=ids["tenant_id"]
        )
        await db.commit()

    assert (await _load_schedule(factory, schedule_id)).status == ScheduleStatus.NORMAL.value
    jobs = await _jobs(factory, ids["tenant_id"])
    job = jobs["cancel_schedule_if_underbooked"]
    assert job["status"] == "pending"
    assert abs((job["run_at"] - (start_at - timedelta(minutes=60))).total_seconds()) < 5
