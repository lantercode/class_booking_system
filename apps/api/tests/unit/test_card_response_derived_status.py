"""读路径派生状态测试（P3-0 / 阶段 2.1 收口）。

`MembershipCardResponse` 统一返回派生状态：时间优先，覆盖 DB status 未及时
改写的脏数据。此处不依赖数据库，直接验证 ORM → 响应体的映射。
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.modules.membership.models import CardStatus, MembershipCard
from app.modules.membership.schemas import MembershipCardResponse


def _orm_card(**overrides) -> MembershipCard:
    now = datetime.now(UTC)
    base = {
        "id": 1,
        "public_id": uuid4(),
        "card_no": None,
        "student_id": 10,
        "product_id": None,
        "card_type": "period",
        "total_credits": None,
        "used_credits": 0,
        "valid_from": now - timedelta(days=3),
        "expire_at": now + timedelta(days=10),
        "validity_days": 30,
        "applicable_course_ids": None,
        "applicable_course_type_code": None,
        "max_weekly_usage": None,
        "status": CardStatus.ACTIVE.value,
        "frozen_at": None,
        "frozen_until": None,
        "frozen_reason": None,
        "cancelled_at": None,
        "cancelled_reason": None,
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    return MembershipCard(**base)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        # PENDING 已到生效时间 → 读路径显示 ACTIVE
        (
            {
                "status": CardStatus.PENDING.value,
                "valid_from": datetime.now(UTC) - timedelta(hours=1),
                "expire_at": datetime.now(UTC) + timedelta(days=10),
            },
            CardStatus.ACTIVE.value,
        ),
        # PENDING 未到生效时间 → 保持 PENDING
        (
            {
                "status": CardStatus.PENDING.value,
                "valid_from": datetime.now(UTC) + timedelta(days=2),
                "expire_at": datetime.now(UTC) + timedelta(days=30),
            },
            CardStatus.PENDING.value,
        ),
        # ACTIVE 但 expire_at 已过（脏数据）→ EXPIRED
        (
            {
                "status": CardStatus.ACTIVE.value,
                "valid_from": datetime.now(UTC) - timedelta(days=40),
                "expire_at": datetime.now(UTC) - timedelta(days=1),
            },
            CardStatus.EXPIRED.value,
        ),
        # FROZEN 冻结期内 → FROZEN
        (
            {
                "status": CardStatus.FROZEN.value,
                "frozen_until": datetime.now(UTC) + timedelta(days=2),
                "expire_at": datetime.now(UTC) + timedelta(days=10),
            },
            CardStatus.FROZEN.value,
        ),
        # FROZEN 冻结到期（脏数据未解冻）→ ACTIVE
        (
            {
                "status": CardStatus.FROZEN.value,
                "frozen_until": datetime.now(UTC) - timedelta(hours=1),
                "expire_at": datetime.now(UTC) + timedelta(days=10),
            },
            CardStatus.ACTIVE.value,
        ),
        # CANCELLED 不可被时间派生覆盖
        (
            {
                "status": CardStatus.CANCELLED.value,
                "cancelled_at": datetime.now(UTC) - timedelta(days=1),
                "expire_at": datetime.now(UTC) - timedelta(days=1),
            },
            CardStatus.CANCELLED.value,
        ),
    ],
)
def test_response_uses_derived_status(overrides, expected):
    resp = MembershipCardResponse.model_validate(_orm_card(**overrides))
    assert resp.status == expected


def test_response_with_naive_datetime_keeps_db_status():
    """naive datetime 不做派生（避免 naive/aware 比较异常），退回 DB 状态。"""
    now = datetime.now(UTC)
    card = _orm_card(
        status=CardStatus.PENDING.value,
        valid_from=(now - timedelta(hours=1)).replace(tzinfo=None),
        expire_at=now + timedelta(days=10),
    )
    resp = MembershipCardResponse.model_validate(card)
    assert resp.status == CardStatus.PENDING.value
