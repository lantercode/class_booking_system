"""F6.11 T6.11.1 会员卡只读端点归属/越权校验（HTTP 集成）。

验收映射（F6.11 安全前置）：
  R-1 卡片详情：学员查本人卡 200 / 查同租户他人卡 403 / 跨租户 404 / 不存在 404
  R-2 卡片详情：admin / super_admin 查本租户任意卡 200
  R-3 卡片详情：teacher（非 admin）查他人卡 403；查本人作为学员的卡 200
  R-4 消费流水：学员不传 card_id 仅见本人卡流水；传他人 card_id 403；
      本人无卡时返回空页；admin 不传 card_id 正常（全租户）
  R-5 卡片列表：学员传他人 student_id 403；不传 student_id 仅返回本人卡

实现口径：端点不挂角色装饰器（混合角色场景），归属校验在 Service 层
（MembershipCardService.get_card_for_requester / list_cards_for_requester /
list_transactions_for_requester）。响应统一信封 code/msg/data。
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.core.tenant_context import set_tenant_id
from app.modules.membership.models import (
    CardStatus,
    CardType,
    MembershipCardTransaction,
    TransactionType,
)
from app.modules.tenant.models import Tenant, TenantStatus
from tests.membership_support import (
    BASE,
    SEED_STUDENT,
    SEED_TEACHER,
    SUPER_ADMIN,
    cleanup,
    create_card,
    create_student,
    db_factory,
    get_seed_ids,
    login,
)
from tests.membership_support import headers as auth_headers

CARDS = f"{BASE}/membership/cards"
TRANSACTIONS = f"{BASE}/membership/transactions"

FORBIDDEN_CARD_MSG = "无权查看该会员卡"
FORBIDDEN_STUDENT_MSG = "无权查看其他学员的会员卡"


@pytest.fixture(scope="function")
async def env():
    async with db_factory() as factory:
        ids = await get_seed_ids(factory)
        yield factory, ids


# ============================================================
# 工具
# ============================================================


def _assert_ok(resp, *, require_data: bool = True):
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    # 项目 success() 默认 msg 为 "ok"（core/response.py）
    assert body["msg"] == "ok", body
    if require_data:
        assert "data" in body, body
    return body["data"]


def _assert_forbidden(resp, expected_msg: str):
    assert resp.status_code == 403, resp.text
    body = resp.json()
    assert body["code"] == 403, body
    assert expected_msg in body["msg"], body
    for leaked in ("Traceback", "SELECT", "postgresql", ".py"):
        assert leaked not in resp.text
    return body


def _assert_not_found(resp):
    assert resp.status_code == 404, resp.text
    body = resp.json()
    msg = body.get("msg") or body.get("detail") or ""
    assert "会员卡不存在" in msg, body
    for leaked in ("Traceback", "SELECT", "postgresql", ".py"):
        assert leaked not in resp.text


async def _fresh_student(client: AsyncClient, factory, tenant_id: int):
    student = await create_student(factory, tenant_id)
    token = await login(client, {"phone": student["phone"], "password": student["password"]})
    return student, token


async def _fresh_admin(client: AsyncClient, factory, tenant_id: int):
    admin = await create_student(factory, tenant_id, role_code="admin")
    token = await login(client, {"phone": admin["phone"], "password": admin["password"]})
    return admin, token


async def _add_txn(
    factory,
    tenant_id: int,
    card_id: int,
    *,
    operation_type: str = TransactionType.ISSUE.value,
    change_amount: int = 1,
    balance_after: int = 1,
) -> int:
    async with factory() as session:
        set_tenant_id(tenant_id)
        txn = MembershipCardTransaction(
            tenant_id=tenant_id,
            card_id=card_id,
            operation_type=operation_type,
            change_amount=change_amount,
            balance_after=balance_after,
            remark=f"T6.11.1 测试流水 {uuid4().hex[:8]}",
        )
        session.add(txn)
        await session.flush()
        txn_id = txn.id
        await session.commit()
    return txn_id


async def _get_card_detail(client: AsyncClient, token: str, card_id: int):
    return await client.get(f"{CARDS}/{card_id}", headers=auth_headers(token))


# ============================================================
# R-1 / R-2 / R-3：卡片详情归属
# ============================================================


@pytest.mark.asyncio
async def test_r1_student_own_card_200(client: AsyncClient, env):
    """R-1：学员查本人卡 → 200 信封，data.id/student_id 正确。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, token = await _fresh_student(client, factory, tid)
    card_id = await create_card(
        factory, tid, student["user_id"],
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value, total_credits=5,
    )
    try:
        data = _assert_ok(await _get_card_detail(client, token, card_id))
        assert data["id"] == card_id
        assert data["student_id"] == student["user_id"]
    finally:
        await cleanup(factory, tid, card_ids=[card_id], student_ids=[student["user_id"]])


@pytest.mark.asyncio
async def test_r1_student_other_card_403(client: AsyncClient, env):
    """R-1：学员查同租户他人卡 → 403「无权查看该会员卡」。"""
    factory, ids = env
    tid = ids["tenant_id"]
    owner, _ = await _fresh_student(client, factory, tid)
    other, other_token = await _fresh_student(client, factory, tid)
    card_id = await create_card(
        factory, tid, owner["user_id"],
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value, total_credits=5,
    )
    try:
        _assert_forbidden(
            await _get_card_detail(client, other_token, card_id), FORBIDDEN_CARD_MSG
        )
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id],
            student_ids=[owner["user_id"], other["user_id"]],
        )


@pytest.mark.asyncio
async def test_r1_cross_tenant_card_404(client: AsyncClient, env):
    """R-1：其他租户的卡 id + 本租户登录态 → 404（不泄露存在性）。"""
    factory, ids = env
    async with factory() as session:
        tenant_b = Tenant(
            name=f"F6.11隔离租户{uuid4().hex[:8]}",
            slug=f"f611-{uuid4().hex[:12]}",
            status=TenantStatus.ACTIVE.value,
        )
        session.add(tenant_b)
        await session.flush()
        tenant_b_id = tenant_b.id
        await session.commit()

    card_b = await create_card(
        factory, tenant_b_id, ids["student_id"],
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value, total_credits=5,
    )
    try:
        token = await login(client, SEED_STUDENT)
        _assert_not_found(await _get_card_detail(client, token, card_b))
    finally:
        await cleanup(factory, tenant_b_id, card_ids=[card_b])
        async with factory() as session:
            await session.execute(delete(Tenant).where(Tenant.id == tenant_b_id))
            await session.commit()


@pytest.mark.asyncio
async def test_r1_card_not_found_404(client: AsyncClient, env):
    """R-1：卡不存在 → 404「会员卡不存在」（admin 也不放行为 200）。"""
    token = await login(client, SUPER_ADMIN)
    _assert_not_found(await _get_card_detail(client, token, 987654321))


@pytest.mark.asyncio
async def test_r2_admin_and_super_admin_any_card_200(client: AsyncClient, env):
    """R-2：admin / super_admin 查本租户任意卡（含他人卡）→ 200。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, _ = await _fresh_student(client, factory, tid)
    admin, admin_token = await _fresh_admin(client, factory, tid)
    super_token = await login(client, SUPER_ADMIN)
    card_id = await create_card(
        factory, tid, student["user_id"],
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value, total_credits=5,
    )
    try:
        assert _assert_ok(await _get_card_detail(client, admin_token, card_id))["id"] == card_id
        assert _assert_ok(await _get_card_detail(client, super_token, card_id))["id"] == card_id
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id],
            student_ids=[student["user_id"], admin["user_id"]],
        )


@pytest.mark.asyncio
async def test_r3_teacher_other_card_403_own_card_200(client: AsyncClient, env):
    """R-3：teacher 查他人卡 403；查「本人作为学员」的卡 200（非 admin 但本人）。"""
    factory, ids = env
    tid = ids["tenant_id"]
    owner, _ = await _fresh_student(client, factory, tid)
    teacher_token = await login(client, SEED_TEACHER)
    teacher_id = ids["teacher_id"]
    other_card = await create_card(
        factory, tid, owner["user_id"],
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value, total_credits=5,
    )
    own_card = await create_card(
        factory, tid, teacher_id,
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value, total_credits=5,
    )
    try:
        _assert_forbidden(
            await _get_card_detail(client, teacher_token, other_card), FORBIDDEN_CARD_MSG
        )
        data = _assert_ok(await _get_card_detail(client, teacher_token, own_card))
        assert data["id"] == own_card
        assert data["student_id"] == teacher_id
    finally:
        await cleanup(
            factory, tid, card_ids=[other_card, own_card],
            student_ids=[owner["user_id"]],
        )


# ============================================================
# R-4：消费流水归属
# ============================================================


@pytest.mark.asyncio
async def test_r4_student_no_card_id_only_own(client: AsyncClient, env):
    """R-4：学员不传 card_id → 仅本人卡流水（他人的卡流水不出现）。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, token = await _fresh_student(client, factory, tid)
    other, _ = await _fresh_student(client, factory, tid)
    own_card = await create_card(
        factory, tid, student["user_id"],
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value, total_credits=5,
    )
    other_card = await create_card(
        factory, tid, other["user_id"],
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value, total_credits=5,
    )
    try:
        own_txns = [
            await _add_txn(factory, tid, own_card, change_amount=1, balance_after=1),
            await _add_txn(factory, tid, own_card, change_amount=-1, balance_after=0),
        ]
        await _add_txn(factory, tid, other_card, change_amount=1, balance_after=1)

        data = _assert_ok(
            await client.get(
                TRANSACTIONS, params={"page_size": 500}, headers=auth_headers(token)
            )
        )
        assert data["total"] == len(own_txns), data
        assert {item["id"] for item in data["items"]} == set(own_txns)
        assert all(item["card_id"] == own_card for item in data["items"])
    finally:
        await cleanup(
            factory, tid, card_ids=[own_card, other_card],
            student_ids=[student["user_id"], other["user_id"]],
        )


@pytest.mark.asyncio
async def test_r4_student_own_card_id_200(client: AsyncClient, env):
    """R-4：学员显式传本人 card_id → 200，仅该卡流水。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, token = await _fresh_student(client, factory, tid)
    card_id = await create_card(
        factory, tid, student["user_id"],
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value, total_credits=5,
    )
    try:
        txn_id = await _add_txn(factory, tid, card_id, change_amount=1, balance_after=1)
        data = _assert_ok(
            await client.get(
                TRANSACTIONS, params={"card_id": card_id}, headers=auth_headers(token)
            )
        )
        assert data["total"] == 1
        assert data["items"][0]["id"] == txn_id
        assert data["items"][0]["card_id"] == card_id
    finally:
        await cleanup(factory, tid, card_ids=[card_id], student_ids=[student["user_id"]])


@pytest.mark.asyncio
async def test_r4_student_other_card_id_403(client: AsyncClient, env):
    """R-4：学员传他人 card_id → 403（归属校验先于查询）。"""
    factory, ids = env
    tid = ids["tenant_id"]
    owner, _ = await _fresh_student(client, factory, tid)
    other, other_token = await _fresh_student(client, factory, tid)
    card_id = await create_card(
        factory, tid, owner["user_id"],
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value, total_credits=5,
    )
    try:
        resp = await client.get(
            TRANSACTIONS, params={"card_id": card_id}, headers=auth_headers(other_token)
        )
        _assert_forbidden(resp, FORBIDDEN_CARD_MSG)
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id],
            student_ids=[owner["user_id"], other["user_id"]],
        )


@pytest.mark.asyncio
async def test_r4_student_without_cards_empty_page(client: AsyncClient, env):
    """R-4：学员名下无卡 → 返回空页（total=0、items=[]），不报错。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, token = await _fresh_student(client, factory, tid)
    try:
        data = _assert_ok(
            await client.get(TRANSACTIONS, headers=auth_headers(token))
        )
        assert data == {"total": 0, "page": 1, "page_size": 20, "items": []}
    finally:
        await cleanup(factory, tid, student_ids=[student["user_id"]])


@pytest.mark.asyncio
async def test_r4_admin_no_card_id_sees_all(client: AsyncClient, env):
    """R-4：admin 不传 card_id → 正常返回全租户流水（含他人卡）。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, _ = await _fresh_student(client, factory, tid)
    other, _ = await _fresh_student(client, factory, tid)
    card_a = await create_card(
        factory, tid, student["user_id"],
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value, total_credits=5,
    )
    card_b = await create_card(
        factory, tid, other["user_id"],
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value, total_credits=5,
    )
    super_token = await login(client, SUPER_ADMIN)
    try:
        txn_ids = [
            await _add_txn(factory, tid, card_a, change_amount=1, balance_after=1),
            await _add_txn(factory, tid, card_b, change_amount=1, balance_after=1),
        ]
        data = _assert_ok(
            await client.get(
                TRANSACTIONS, params={"page_size": 500}, headers=auth_headers(super_token)
            )
        )
        seen = {item["id"] for item in data["items"] if item["card_id"] in (card_a, card_b)}
        assert seen == set(txn_ids), data
        assert data["total"] >= len(txn_ids)
    finally:
        await cleanup(
            factory, tid, card_ids=[card_a, card_b],
            student_ids=[student["user_id"], other["user_id"]],
        )


# ============================================================
# R-5：卡片列表归属
# ============================================================


@pytest.mark.asyncio
async def test_r5_student_other_student_id_403(client: AsyncClient, env):
    """R-5：学员显式传他人 student_id → 403「无权查看其他学员的会员卡」。"""
    factory, ids = env
    tid = ids["tenant_id"]
    owner, _ = await _fresh_student(client, factory, tid)
    other, other_token = await _fresh_student(client, factory, tid)
    card_id = await create_card(
        factory, tid, owner["user_id"],
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value, total_credits=5,
    )
    try:
        resp = await client.get(
            CARDS, params={"student_id": owner["user_id"]}, headers=auth_headers(other_token)
        )
        _assert_forbidden(resp, FORBIDDEN_STUDENT_MSG)
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id],
            student_ids=[owner["user_id"], other["user_id"]],
        )


@pytest.mark.asyncio
async def test_r5_student_no_student_id_only_own(client: AsyncClient, env):
    """R-5：学员不传 student_id → 仅本人卡；筛选参数原样透传（status 生效）。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, token = await _fresh_student(client, factory, tid)
    other, _ = await _fresh_student(client, factory, tid)
    own_a = await create_card(
        factory, tid, student["user_id"],
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value, total_credits=5,
    )
    own_b = await create_card(
        factory, tid, student["user_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.PENDING.value,
    )
    other_card = await create_card(
        factory, tid, other["user_id"],
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value, total_credits=5,
    )
    try:
        data = _assert_ok(
            await client.get(CARDS, params={"page_size": 500}, headers=auth_headers(token))
        )
        assert {item["id"] for item in data["items"]} == {own_a, own_b}
        assert all(item["student_id"] == student["user_id"] for item in data["items"])

        # status=0（待激活/未生效）筛选原样透传，只命中本人 PENDING 卡
        filtered = _assert_ok(
            await client.get(
                CARDS, params={"status": CardStatus.PENDING.value}, headers=auth_headers(token)
            )
        )
        assert [item["id"] for item in filtered["items"]] == [own_b]
    finally:
        await cleanup(
            factory, tid, card_ids=[own_a, own_b, other_card],
            student_ids=[student["user_id"], other["user_id"]],
        )


@pytest.mark.asyncio
async def test_r5_admin_filter_any_student_200(client: AsyncClient, env):
    """R-5：admin 传他人 student_id → 200（行为与既有 list_cards 一致）。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, _ = await _fresh_student(client, factory, tid)
    admin, admin_token = await _fresh_admin(client, factory, tid)
    card_id = await create_card(
        factory, tid, student["user_id"],
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value, total_credits=5,
    )
    try:
        data = _assert_ok(
            await client.get(
                CARDS,
                params={"student_id": student["user_id"], "page_size": 500},
                headers=auth_headers(admin_token),
            )
        )
        assert data["total"] >= 1
        assert card_id in {item["id"] for item in data["items"]}
        assert all(item["student_id"] == student["user_id"] for item in data["items"])
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id],
            student_ids=[student["user_id"], admin["user_id"]],
        )
