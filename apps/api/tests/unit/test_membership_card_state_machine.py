"""F6.3 会员卡状态机纯函数单元测试（T6.3.7）。

不依赖数据库/Redis，直接构造未持久化的 ORM 对象验证判定与区间计算。
"""

from datetime import UTC, datetime

from app.modules.membership.models import CardStatus, CardType, MembershipCard
from app.modules.membership.service import membership_card_service


def make_card(**overrides) -> MembershipCard:
    defaults = {
        "card_type": CardType.PERIOD.value,
        "status": CardStatus.PENDING.value,
        "total_credits": None,
        "used_credits": 0,
        "valid_from": None,
        "expire_at": None,
        "applicable_course_type_code": None,
        "applicable_course_ids": None,
    }
    defaults.update(overrides)
    return MembershipCard(**defaults)


def test_is_period_pending_bookable_true_for_d9_card():
    card = make_card(status=CardStatus.PENDING.value, valid_from=None)
    assert membership_card_service.is_period_pending_bookable(card) is True


def test_is_period_pending_bookable_false_when_valid_from_set():
    card = make_card(
        status=CardStatus.PENDING.value,
        valid_from=datetime(2026, 10, 22, tzinfo=UTC),
    )
    assert membership_card_service.is_period_pending_bookable(card) is False


def test_is_period_pending_bookable_false_for_non_pending_statuses():
    for status in (
        CardStatus.ACTIVE.value,
        CardStatus.FROZEN.value,
        CardStatus.EXPIRED.value,
        CardStatus.CANCELLED.value,
    ):
        card = make_card(status=status, valid_from=None)
        assert membership_card_service.is_period_pending_bookable(card) is False


def test_calc_expected_interval_inclusive():
    valid_from = datetime(2026, 10, 22, 0, 0, 0, tzinfo=UTC)
    expire_at = membership_card_service._calc_expire_at(valid_from, 3)
    assert valid_from.date().isoformat() == "2026-10-22"
    assert expire_at.date().isoformat() == "2026-10-24"
    assert (expire_at.hour, expire_at.minute, expire_at.second) == (23, 59, 59)


def test_interval_overlap_closed_boundary_counts_as_overlap():
    a = make_card(
        valid_from=datetime(2026, 10, 22, 0, 0, 0, tzinfo=UTC),
        expire_at=datetime(2026, 10, 24, 23, 59, 59, tzinfo=UTC),
    )
    b = make_card(
        valid_from=datetime(2026, 10, 24, 0, 0, 0, tzinfo=UTC),
        expire_at=datetime(2026, 10, 26, 23, 59, 59, tzinfo=UTC),
    )
    assert membership_card_service._check_time_overlap(a, b) is True
    assert membership_card_service._check_time_overlap(b, a) is True


def test_interval_no_overlap_when_adjacent_days():
    a = make_card(
        valid_from=datetime(2026, 10, 22, 0, 0, 0, tzinfo=UTC),
        expire_at=datetime(2026, 10, 24, 23, 59, 59, tzinfo=UTC),
    )
    b = make_card(
        valid_from=datetime(2026, 10, 25, 0, 0, 0, tzinfo=UTC),
        expire_at=datetime(2026, 10, 27, 23, 59, 59, tzinfo=UTC),
    )
    assert membership_card_service._check_time_overlap(a, b) is False


def test_bookable_on_expire_date_boundary():
    expire_at = datetime(2026, 10, 24, 23, 59, 59, tzinfo=UTC)
    card = make_card(
        status=CardStatus.ACTIVE.value,
        valid_from=datetime(2026, 10, 22, 0, 0, 0, tzinfo=UTC),
        expire_at=expire_at,
    )
    same_day = datetime(2026, 10, 24, 10, 0, 0, tzinfo=UTC)
    next_day = datetime(2026, 10, 25, 10, 0, 0, tzinfo=UTC)

    assert (
        membership_card_service.is_bookable_card(
            card, schedule_start_at=same_day, course_id=1, course_type_code=None
        )
        is True
    )
    assert (
        membership_card_service.is_bookable_card(
            card, schedule_start_at=next_day, course_id=1, course_type_code=None
        )
        is False
    )


def test_period_pending_bookable_but_frozen_not():
    pending = make_card(status=CardStatus.PENDING.value)
    assert (
        membership_card_service.is_bookable_card(
            pending,
            schedule_start_at=datetime(2026, 10, 22, 10, tzinfo=UTC),
            course_id=1,
            course_type_code="regular",
        )
        is True
    )

    frozen = make_card(status=CardStatus.FROZEN.value)
    assert (
        membership_card_service.is_bookable_card(
            frozen,
            schedule_start_at=datetime(2026, 10, 22, 10, tzinfo=UTC),
            course_id=1,
            course_type_code="regular",
        )
        is False
    )


def test_course_applicability_mismatch_rejected():
    card = make_card(
        status=CardStatus.PENDING.value,
        applicable_course_type_code="regular",
    )
    # 课程无类型时，卡有限制 → 拒绝（UNKNOWN-8 的建议口径）
    assert (
        membership_card_service.is_bookable_card(
            card,
            schedule_start_at=datetime(2026, 10, 22, 10, tzinfo=UTC),
            course_id=1,
            course_type_code=None,
        )
        is False
    )
    assert (
        membership_card_service.is_bookable_card(
            card,
            schedule_start_at=datetime(2026, 10, 22, 10, tzinfo=UTC),
            course_id=1,
            course_type_code="private",
        )
        is False
    )
    assert (
        membership_card_service.is_bookable_card(
            card,
            schedule_start_at=datetime(2026, 10, 22, 10, tzinfo=UTC),
            course_id=1,
            course_type_code="regular",
        )
        is True
    )
