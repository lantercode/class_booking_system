"""预约创建 Idempotency-Key 幂等验证脚本。

两种模式：

1) 本地模式（默认）：自建临时课程/排期/次卡 → 同 key 连发两次 → HTTP + 数据库双重校验 → 自动清理。
       cd apps/api
       PYTHONPATH=src .venv/bin/python scripts/verify_booking_idempotency.py

2) 远程模式：只做 HTTP 校验，使用已有学员与排期，不写库、不建临时数据。
       API_BASE=https://api.example.com/api/v1 \\
       TENANT_SLUG=dance-school \\
       STUDENT_PHONE=13900000000 STUDENT_PASSWORD=****** \\
       SCHEDULE_ID=123 \\
       PYTHONPATH=src .venv/bin/python scripts/verify_booking_idempotency.py --remote

可选环境变量：
    MEMBERSHIP_CARD_ID   指定卡（远程模式建议显式传，避免自动选卡不稳定）
    CLEANUP=1            远程模式验证完自动取消该预约（默认 0，保留现场便于核对）

退出码：0 = 全部通过；1 = 存在失败项。
"""

import argparse
import asyncio
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta

import httpx

DEFAULT_API = "http://localhost:8000/api/v1"
SCOPE = "booking.create"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    RESULTS.append((name, passed, detail))
    print(f"  {'✅' if passed else '❌'} {name}{(' — ' + detail) if detail else ''}")


def env(name: str, default: str = "") -> str:
    import os

    return os.getenv(name, default)


async def login(client: httpx.AsyncClient, api: str, tenant: str, phone: str, pwd: str) -> str:
    resp = await client.post(
        f"{api}/auth/login",
        json={"tenant_slug": tenant, "phone": phone, "password": pwd},
        headers={"x-tenant-slug": tenant},
    )
    body = resp.json()
    token = ((body or {}).get("data") or {}).get("access_token")
    if resp.status_code != 200 or not token:
        raise SystemExit(f"登录失败: HTTP {resp.status_code} {body}")
    print(f"[1] 登录成功: {phone} (token len={len(token)})")
    return token


async def post_booking(
    client: httpx.AsyncClient, api: str, headers: dict, payload: dict
) -> httpx.Response:
    return await client.post(f"{api}/bookings/", json=payload, headers=headers)


# ------------------------------- 远程模式 -------------------------------


async def run_remote() -> int:
    api = env("API_BASE", DEFAULT_API).rstrip("/")
    tenant = env("TENANT_SLUG", "dance-school")
    phone = env("STUDENT_PHONE")
    pwd = env("STUDENT_PASSWORD")
    schedule_id = env("SCHEDULE_ID")
    card_id = env("MEMBERSHIP_CARD_ID")
    cleanup = env("CLEANUP", "0") == "1"
    if not (phone and pwd and schedule_id):
        raise SystemExit("远程模式必须提供 STUDENT_PHONE / STUDENT_PASSWORD / SCHEDULE_ID")

    payload: dict = {"schedule_id": int(schedule_id)}
    if card_id:
        payload["membership_card_id"] = int(card_id)

    async with httpx.AsyncClient(timeout=20) as client:
        token = await login(client, api, tenant, phone, pwd)
        headers = {"x-tenant-slug": tenant, "Authorization": f"Bearer {token}"}
        key = str(uuid.uuid4())
        headers["Idempotency-Key"] = key
        print(f"[2] 排期={schedule_id} 幂等键={key}")

        r1 = await post_booking(client, api, headers, payload)
        r2 = await post_booking(client, api, headers, payload)
        print(f"[3] 首次 HTTP={r1.status_code} msg={(r1.json() or {}).get('msg')}")
        print(f"[4] 重放 HTTP={r2.status_code} msg={(r2.json() or {}).get('msg')}")

        id1 = ((r1.json() or {}).get("data") or {}).get("id")
        id2 = ((r2.json() or {}).get("data") or {}).get("id")
        check("首次创建返回 201", r1.status_code == 201, f"实际 {r1.status_code}")
        check("同 key 同参数返回 200", r2.status_code == 200, f"实际 {r2.status_code}")
        check("重放返回同一 booking_id", id1 == id2 and id1 is not None, f"{id1} vs {id2}")

        if cleanup and id1:
            rc = await client.post(
                f"{api}/bookings/cancel",
                json={"schedule_id": int(schedule_id), "reason": "幂等验证清理"},
                headers={"x-tenant-slug": tenant, "Authorization": f"Bearer {token}"},
            )
            print(f"[5] 清理取消 HTTP={rc.status_code}")

    return report()


# ------------------------------- 本地模式 -------------------------------


async def run_local() -> int:
    from sqlalchemy import delete, func, select

    from app.core.database import SessionLocal
    from app.core.tenant_context import set_tenant_id
    from app.modules.booking.models import Booking, IdempotencyKey
    from app.modules.course.models import Course
    from app.modules.membership.models import (
        CardStatus,
        CardType,
        MembershipCard,
        MembershipCardTransaction,
    )
    from app.modules.schedule.models import CourseSchedule, ScheduleStatus
    from app.modules.task.models import JobQueue
    from app.modules.tenant.models import Tenant
    from app.modules.user.models import User

    api = env("API_BASE", DEFAULT_API).rstrip("/")
    tenant_slug = env("TENANT_SLUG", "dance-school")
    phone = env("STUDENT_PHONE", "13900139001")
    pwd = env("STUDENT_PASSWORD", "Test@123456")
    marker = uuid.uuid4().hex[:8]
    created: dict[str, int] = {}

    async with httpx.AsyncClient(timeout=20) as client:
        token = await login(client, api, tenant_slug, phone, pwd)

    async with SessionLocal() as db:
        tenant_id = (
            await db.execute(select(Tenant.id).where(Tenant.slug == tenant_slug))
        ).scalar_one()
    async with SessionLocal() as db:
        set_tenant_id(tenant_id)
        student_id = (
            await db.execute(select(User.id).where(User.phone == phone))
        ).scalar_one()
        teacher_id = (
            await db.execute(select(User.id).where(User.tenant_id == tenant_id).limit(1))
        ).scalar_one()

    try:
        async with SessionLocal() as db:
            set_tenant_id(tenant_id)
            course = Course(
                tenant_id=tenant_id,
                name=f"幂等验证课程-{marker}",
                course_type_code="regular",
                duration_minutes=60,
                price=0,
                required_credits=1,
            )
            db.add(course)
            await db.flush()
            created["course_id"] = course.id

            start_at = datetime.now(UTC) + timedelta(hours=3)
            schedule_ids: list[int] = []
            for i in range(2):
                schedule = CourseSchedule(
                    tenant_id=tenant_id,
                    course_id=course.id,
                    teacher_id=teacher_id,
                    start_at=start_at + timedelta(hours=i),
                    end_at=start_at + timedelta(hours=i + 1),
                    capacity=10,
                    booked_count=0,
                    status=ScheduleStatus.NORMAL.value,
                    notes=f"idem-{marker}-{i}",
                )
                db.add(schedule)
                await db.flush()
                schedule_ids.append(schedule.id)
            created["schedule1"], created["schedule2"] = schedule_ids

            card = MembershipCard(
                tenant_id=tenant_id,
                card_no=f"MC{datetime.now(UTC):%Y%m%d}{random.randint(0, 999999999):09d}",
                student_id=student_id,
                card_type=CardType.COUNT.value,
                total_credits=10,
                used_credits=0,
                valid_from=datetime.now(UTC) - timedelta(days=1),
                expire_at=datetime.now(UTC) + timedelta(days=30),
                applicable_course_type_code="regular",
                status=CardStatus.ACTIVE.value,
            )
            db.add(card)
            await db.flush()
            created["card_id"] = card.id
            await db.commit()
        print(
            f"[2] 临时数据: course={created['course_id']} "
            f"schedules={created['schedule1']}/{created['schedule2']} "
            f"card={created['card_id']}"
        )

        key = str(uuid.uuid4())
        headers = {
            "x-tenant-slug": tenant_slug,
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": key,
        }
        payload = {"schedule_id": created["schedule1"], "membership_card_id": created["card_id"]}
        other_payload = {
            "schedule_id": created["schedule2"],
            "membership_card_id": created["card_id"],
        }

        async with httpx.AsyncClient(timeout=20) as client:
            r1 = await post_booking(client, api, headers, payload)
            r2 = await post_booking(client, api, headers, payload)
            r3 = await post_booking(client, api, headers, other_payload)
        print(f"[3] 首次 HTTP={r1.status_code} msg={(r1.json() or {}).get('msg')}")
        print(f"[4] 重放 HTTP={r2.status_code} msg={(r2.json() or {}).get('msg')}")
        print(f"[5] 同 key 异参数 HTTP={r3.status_code} msg={(r3.json() or {}).get('msg')}")

        id1 = ((r1.json() or {}).get("data") or {}).get("id")
        id2 = ((r2.json() or {}).get("data") or {}).get("id")
        created["booking_id"] = id1 or 0

        check("首次创建返回 201", r1.status_code == 201, f"实际 {r1.status_code}")
        check("同 key 同参数返回 200", r2.status_code == 200, f"实际 {r2.status_code}")
        check("重放返回同一 booking_id", id1 == id2 and id1 is not None, f"{id1} vs {id2}")
        check("同 key 异参数返回 409", r3.status_code == 409, f"实际 {r3.status_code}")

        async with SessionLocal() as db:
            set_tenant_id(tenant_id)
            booking_cnt = (
                await db.execute(
                    select(func.count())
                    .select_from(Booking)
                    .where(
                        Booking.tenant_id == tenant_id,
                        Booking.student_id == student_id,
                        Booking.schedule_id == created["schedule1"],
                    )
                )
            ).scalar_one()
            txn_cnt = (
                await db.execute(
                    select(func.count())
                    .select_from(MembershipCardTransaction)
                    .where(
                        MembershipCardTransaction.tenant_id == tenant_id,
                        MembershipCardTransaction.idempotency_key
                        == f"booking_{created['booking_id']}_deduct",
                    )
                )
            ).scalar_one()
            idem_rows, idem_booking_id = (
                await db.execute(
                    select(
                        func.count(),
                        func.min(IdempotencyKey.booking_id),
                    ).where(
                        IdempotencyKey.tenant_id == tenant_id,
                        IdempotencyKey.scope == SCOPE,
                        IdempotencyKey.key == key,
                    )
                )
            ).one()
            booked_count = (
                await db.execute(
                    select(CourseSchedule.booked_count).where(
                        CourseSchedule.id == created["schedule1"]
                    )
                )
            ).scalar_one()
            used_credits = (
                await db.execute(
                    select(MembershipCard.used_credits).where(
                        MembershipCard.id == created["card_id"]
                    )
                )
            ).scalar_one()

        check("该排期只有 1 笔预约", booking_cnt == 1, f"实际 {booking_cnt}")
        check("扣次流水只有 1 条", txn_cnt == 1, f"实际 {txn_cnt}")
        check("扣次只发生一次", used_credits == 1, f"used_credits={used_credits}")
        check(
            "幂等记录唯一且指向该预约",
            idem_rows == 1 and idem_booking_id == created["booking_id"],
            f"rows={idem_rows} booking_id={idem_booking_id}",
        )
        check("排期名额只 +1", booked_count == 1, f"booked_count={booked_count}")

    finally:
        async with SessionLocal() as db:
            set_tenant_id(tenant_id)
            if "schedule1" in created:
                ids = [created[k] for k in ("schedule1", "schedule2") if k in created]
                await db.execute(
                    delete(IdempotencyKey).where(
                        IdempotencyKey.tenant_id == tenant_id,
                        IdempotencyKey.scope == SCOPE,
                        IdempotencyKey.key == key,
                    )
                )
                await db.execute(
                    delete(Booking).where(
                        Booking.tenant_id == tenant_id, Booking.schedule_id.in_(ids)
                    )
                )
                if created.get("booking_id"):
                    await db.execute(
                        delete(MembershipCardTransaction).where(
                            MembershipCardTransaction.tenant_id == tenant_id,
                            MembershipCardTransaction.idempotency_key
                            == f"booking_{created['booking_id']}_deduct",
                        )
                    )
                job_keys = [f"schedule:{sid}:complete" for sid in ids] + [
                    f"schedule:{sid}:cancel_underbooked" for sid in ids
                ]
                await db.execute(
                    delete(JobQueue).where(
                        JobQueue.tenant_id == tenant_id,
                        JobQueue.idempotency_key.in_(job_keys),
                    )
                )
                await db.execute(
                    delete(CourseSchedule).where(
                        CourseSchedule.tenant_id == tenant_id,
                        CourseSchedule.id.in_(ids),
                    )
                )
            if "card_id" in created:
                await db.execute(
                    delete(MembershipCard).where(
                        MembershipCard.tenant_id == tenant_id,
                        MembershipCard.id == created["card_id"],
                    )
                )
            if "course_id" in created:
                await db.execute(
                    delete(Course).where(
                        Course.tenant_id == tenant_id, Course.id == created["course_id"]
                    )
                )
            await db.commit()
        print("[6] 临时数据已清理")

    return report()


def report() -> int:
    passed = sum(1 for _, ok_, _ in RESULTS if ok_)
    total = len(RESULTS)
    print("-" * 46)
    print(f"结果: {passed}/{total} 通过")
    print("✅ 幂等验证通过" if passed == total else "❌ 存在失败项")
    return 0 if passed == total else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="预约创建 Idempotency-Key 幂等验证")
    parser.add_argument(
        "--remote",
        action="store_true",
        help="远程模式：只做 HTTP 校验，不建临时数据（需 SCHEDULE_ID 等环境变量）",
    )
    args = parser.parse_args()
    return asyncio.run(run_remote() if args.remote else run_local())


if __name__ == "__main__":
    sys.exit(main())
