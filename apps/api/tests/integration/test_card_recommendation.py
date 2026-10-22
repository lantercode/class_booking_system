"""F6.6 多卡默认推荐策略集成测试（HTTP + PostgreSQL）。

覆盖 acceptance C-1~C-9、E-2、E-4。所有数据通过 membership_support 创建，
并在 finally 中按外键顺序清理，避免污染其他用例。
"""

from datetime import timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.modules.membership.models import CardStatus, CardType
from app.modules.tenant.models import Tenant, TenantStatus
from tests.membership_support import (
    BASE,
    SEED_STUDENT,
    TENANT_HEADERS,
    cleanup,
    count_transactions,
    create_card,
    create_course,
    create_schedule,
    create_student,
    day_end,
    day_start,
    db_factory,
    fetch_card,
    future_start,
    get_seed_ids,
    login,
)
from tests.membership_support import (
    headers as auth_headers,
)

RECOMMEND = f"{BASE}/membership/recommend-card"


@pytest.fixture(scope="function")
async def env():
    async with db_factory() as factory:
        ids = await get_seed_ids(factory)
        yield factory, ids


async def _recommend(client: AsyncClient, token: str, schedule_id: int):
    return await client.get(
        RECOMMEND, params={"schedule_id": schedule_id}, headers=auth_headers(token)
    )


async def _fresh_student(client: AsyncClient, factory, tenant_id: int):
    student = await create_student(factory, tenant_id)
    token = await login(client, {"phone": student["phone"], "password": student["password"]})
    return student, token


async def _create_other_tenant(factory) -> int:
    async with factory() as session:
        tenant = Tenant(
            name=f"F6.6隔离租户{uuid4().hex[:8]}",
            slug=f"f66-{uuid4().hex[:12]}",
            status=TenantStatus.ACTIVE.value,
        )
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        await session.commit()
    return tenant_id


async def _delete_tenant(factory, tenant_id: int) -> None:
    async with factory() as session:
        await session.execute(delete(Tenant).where(Tenant.id == tenant_id))
        await session.commit()


def _data(resp) -> dict:
    return resp.json()["data"]


def _msg(resp) -> str:
    body = resp.json()
    return body.get("msg") or body.get("detail") or ""


@pytest.mark.asyncio
async def test_c1_c2_sorted_recommendation_is_stable(client: AsyncClient, env):
    """C-1/C-2：D6 排序、recommended_card_id、重复请求顺序一致。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, token = await _fresh_student(client, factory, tid)
    course_id = await create_course(factory, tid, name="F6.6排序课")
    schedule_start = future_start(3, hour=10)
    schedule_id = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=schedule_start,
    )
    expire_same = day_end(schedule_start)
    expire_later = day_end(schedule_start + timedelta(days=2))
    later = await create_card(
        factory, tid, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=10,
        expire_at=expire_later,
    )
    more = await create_card(
        factory, tid, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=6, used_credits=1,
        expire_at=expire_same,
    )
    fewer = await create_card(
        factory, tid, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=2, used_credits=1,
        expire_at=expire_same,
    )
    try:
        resp = await _recommend(client, token, schedule_id)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["code"] == 0
        data = _data(resp)

        assert data["schedule_id"] == schedule_id
        assert [c["id"] for c in data["available_cards"]] == [fewer, more, later]
        assert data["recommended_card_id"] == fewer
        assert data["available_cards"][0]["remaining_credits"] == 1
        assert data["message"] is None

        # 固定卡集合重复请求，顺序与推荐 id 不变
        again = await _recommend(client, token, schedule_id)
        assert again.status_code == 200, again.text
        assert [c["id"] for c in _data(again)["available_cards"]] == [
            fewer, more, later
        ]
        assert _data(again)["recommended_card_id"] == fewer
    finally:
        await cleanup(
            factory, tid, card_ids=[later, more, fewer],
            schedule_ids=[schedule_id], course_ids=[course_id],
            student_ids=[student["user_id"]],
        )


@pytest.mark.asyncio
async def test_c3_exclusion_rules_end_to_end(client: AsyncClient, env):
    """C-3：过期/冻结/作废/未激活/未生效/用尽/类型或课程不匹配均排除。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, token = await _fresh_student(client, factory, tid)
    course_id = await create_course(
        factory, tid, course_type_code="regular", name="F6.6排除课"
    )
    schedule_start = future_start(4, hour=10)
    schedule_id = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=schedule_start,
    )

    cards = [
        await create_card(
            factory, tid, student["user_id"], card_type=CardType.COUNT.value,
            status=CardStatus.ACTIVE.value, total_credits=5,
            expire_at=day_end(schedule_start - timedelta(days=3)),
        ),  # 已过期
        await create_card(
            factory, tid, student["user_id"], card_type=CardType.COUNT.value,
            status=CardStatus.FROZEN.value, total_credits=5,
        ),  # 已冻结
        await create_card(
            factory, tid, student["user_id"], card_type=CardType.COUNT.value,
            status=CardStatus.CANCELLED.value, total_credits=5,
        ),  # 已作废
        await create_card(
            factory, tid, student["user_id"], card_type=CardType.COUNT.value,
            status=CardStatus.PENDING.value, total_credits=5,
        ),  # 未激活次卡
        await create_card(
            factory, tid, student["user_id"], card_type=CardType.COUNT.value,
            status=CardStatus.ACTIVE.value, total_credits=5,
            valid_from=day_start(schedule_start + timedelta(days=1)),
        ),  # 尚未生效
        await create_card(
            factory, tid, student["user_id"], card_type=CardType.COUNT.value,
            status=CardStatus.ACTIVE.value, total_credits=1, used_credits=1,
        ),  # 次卡用完
        await create_card(
            factory, tid, student["user_id"], card_type=CardType.COUNT.value,
            status=CardStatus.ACTIVE.value, total_credits=5,
            applicable_course_type_code="other",
        ),  # 课程类型不匹配
        await create_card(
            factory, tid, student["user_id"], card_type=CardType.COUNT.value,
            status=CardStatus.ACTIVE.value, total_credits=5,
            applicable_course_ids=[course_id + 100000],
        ),  # 指定课程不匹配
    ]
    valid = await create_card(
        factory, tid, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5,
        expire_at=day_end(schedule_start + timedelta(days=1)),
    )
    cards.append(valid)
    try:
        resp = await _recommend(client, token, schedule_id)
        assert resp.status_code == 200, resp.text
        data = _data(resp)
        assert [c["id"] for c in data["available_cards"]] == [valid]
        assert data["recommended_card_id"] == valid
        assert data["message"] is None
    finally:
        await cleanup(
            factory, tid, card_ids=cards, schedule_ids=[schedule_id],
            course_ids=[course_id], student_ids=[student["user_id"]],
        )


@pytest.mark.asyncio
async def test_c4_all_cards_excluded_returns_reason_message(client: AsyncClient, env):
    """C-4：全部排除 → 200、null、空列表、聚合原因。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, token = await _fresh_student(client, factory, tid)
    course_id = await create_course(factory, tid, name="F6.6空态课")
    schedule_start = future_start(3, hour=10)
    schedule_id = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=schedule_start,
    )
    expired = await create_card(
        factory, tid, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5,
        expire_at=day_end(schedule_start - timedelta(days=2)),
    )
    frozen = await create_card(
        factory, tid, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.FROZEN.value, total_credits=5,
    )
    try:
        resp = await _recommend(client, token, schedule_id)
        assert resp.status_code == 200, resp.text
        data = _data(resp)
        assert data["recommended_card_id"] is None
        assert data["available_cards"] == []
        assert data["message"].startswith("暂无可用会员卡：")
        assert "已过期" in data["message"]
        assert "已冻结" in data["message"]
    finally:
        await cleanup(
            factory, tid, card_ids=[expired, frozen],
            schedule_ids=[schedule_id], course_ids=[course_id],
            student_ids=[student["user_id"]],
        )


@pytest.mark.asyncio
async def test_c5_student_without_cards(client: AsyncClient, env):
    """C-5：无卡学员 → 200 且 message=您还没有会员卡。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, token = await _fresh_student(client, factory, tid)
    course_id = await create_course(factory, tid, name="F6.6无卡课")
    schedule_id = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=11),
    )
    try:
        resp = await _recommend(client, token, schedule_id)
        assert resp.status_code == 200, resp.text
        data = _data(resp)
        assert data["recommended_card_id"] is None
        assert data["available_cards"] == []
        assert data["message"] == "您还没有会员卡"
    finally:
        await cleanup(
            factory, tid, schedule_ids=[schedule_id], course_ids=[course_id],
            student_ids=[student["user_id"]],
        )


@pytest.mark.asyncio
async def test_c6_unauthenticated_returns_401(client: AsyncClient):
    """C-6：无 Token → 401。"""
    resp = await client.get(
        RECOMMEND, params={"schedule_id": 1}, headers=TENANT_HEADERS
    )
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_c7_missing_schedule_returns_404(client: AsyncClient, env):
    """C-7 / E-4：排期不存在 → 404 且不泄露内部信息。"""
    _factory, _ids = env
    token = await login(client, SEED_STUDENT)
    resp = await _recommend(client, token, 987654321)
    assert resp.status_code == 404, resp.text
    body = resp.text
    assert "排期不存在" in _msg(resp)
    for leaked in ("Traceback", "SELECT", "postgresql", "127.0.0.1", ".py"):
        assert leaked not in body


@pytest.mark.asyncio
async def test_c8_cross_tenant_schedule_returns_404(client: AsyncClient, env):
    """C-8 / E-4：其他租户排期 → 404，不泄露排期信息。"""
    factory, ids = env
    tenant_b = await _create_other_tenant(factory)
    course_b = await create_course(factory, tenant_b)
    schedule_b = await create_schedule(
        factory, tenant_b, course_id=course_b, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=2),
    )
    try:
        token = await login(client, SEED_STUDENT)
        resp = await _recommend(client, token, schedule_b)
        assert resp.status_code == 404, resp.text
        assert "排期不存在" in _msg(resp)
        assert str(schedule_b) not in resp.text
        for leaked in ("Traceback", "SELECT", "postgresql", "127.0.0.1"):
            assert leaked not in resp.text
    finally:
        await cleanup(factory, tenant_b, schedule_ids=[schedule_b], course_ids=[course_b])
        await _delete_tenant(factory, tenant_b)


@pytest.mark.asyncio
async def test_c9_recommend_is_read_only(client: AsyncClient, env):
    """C-9：调用前后卡状态、已用次数与流水均不变。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, token = await _fresh_student(client, factory, tid)
    course_id = await create_course(factory, tid, name="F6.6只读课")
    schedule_id = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=10),
    )
    card_id = await create_card(
        factory, tid, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5, used_credits=1,
        expire_at=day_end(future_start(5, hour=10)),
    )
    try:
        before = await fetch_card(factory, tid, card_id)
        before_txns = await count_transactions(factory, tid, card_id)

        resp = await _recommend(client, token, schedule_id)
        assert resp.status_code == 200, resp.text
        assert _data(resp)["recommended_card_id"] == card_id

        after = await fetch_card(factory, tid, card_id)
        assert after.status == before.status
        assert after.used_credits == before.used_credits
        assert after.total_credits == before.total_credits
        assert after.valid_from == before.valid_from
        assert after.expire_at == before.expire_at
        assert await count_transactions(factory, tid, card_id) == before_txns == 0
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id], schedule_ids=[schedule_id],
            course_ids=[course_id], student_ids=[student["user_id"]],
        )


@pytest.mark.asyncio
async def test_e2_other_students_cards_not_returned(client: AsyncClient, env):
    """E-2：同租户两学员，只返回当前登录学员本人的卡。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student_a, token_a = await _fresh_student(client, factory, tid)
    student_b, _token_b = await _fresh_student(client, factory, tid)
    course_id = await create_course(factory, tid, name="F6.6隔离课")
    schedule_id = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=10),
    )
    card_a = await create_card(
        factory, tid, student_a["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5,
    )
    card_b = await create_card(
        factory, tid, student_b["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5,
    )
    try:
        resp = await _recommend(client, token_a, schedule_id)
        assert resp.status_code == 200, resp.text
        available_ids = [c["id"] for c in _data(resp)["available_cards"]]
        assert available_ids == [card_a]
        assert card_b not in available_ids
    finally:
        await cleanup(
            factory, tid, card_ids=[card_a, card_b],
            schedule_ids=[schedule_id], course_ids=[course_id],
            student_ids=[student_a["user_id"], student_b["user_id"]],
        )
