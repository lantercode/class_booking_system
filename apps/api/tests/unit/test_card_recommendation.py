"""F6.6 多卡默认推荐策略纯逻辑单测（不建库、不依赖 Redis）。

覆盖 acceptance B-1~B-10 与 D-7 的判定部分：D6 排序、共享不可用原因、
期卡 PENDING 两分支、排期日边界、空态文案聚合、未知卡类型。
"""

from datetime import UTC, datetime

from app.modules.membership.models import CardStatus, CardType, MembershipCard
from app.modules.membership.service import MembershipCardService

SCHEDULE_START = datetime(2026, 10, 22, 10, 0, tzinfo=UTC)
COURSE_ID = 10
COURSE_TYPE = "regular"

service = MembershipCardService()


def make_card(**overrides) -> MembershipCard:
    """构造未持久化的 ORM 会员卡（默认可用次卡）。"""
    defaults = {
        "card_type": CardType.COUNT.value,
        "status": CardStatus.ACTIVE.value,
        "total_credits": 10,
        "used_credits": 0,
        "valid_from": None,
        "expire_at": None,
        "applicable_course_type_code": None,
        "applicable_course_ids": None,
    }
    defaults.update(overrides)
    return MembershipCard(**defaults)


def make_dict(card_id: int, **overrides) -> dict:
    """构造推荐链路使用的卡片 dict（与 get_all_cards_by_student 同构）。"""
    data = {
        "id": card_id,
        "card_type": CardType.COUNT.value,
        "status": CardStatus.ACTIVE.value,
        "total_credits": 10,
        "used_credits": 0,
        "remaining_credits": 10,
        "valid_from": None,
        "expire_at": None,
        "applicable_course_type_code": None,
        "applicable_course_ids": None,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    data.update(overrides)
    return data


def sorted_ids(cards: list[dict]) -> list[int]:
    return [card["id"] for card in sorted(cards, key=service._recommend_sort_key)]


# ============================================================
# B-1 ~ B-5：D6 排序
# ============================================================


def test_b1_expire_at_ascending():
    cards = [
        make_dict(1, expire_at=datetime(2026, 10, 30, tzinfo=UTC)),
        make_dict(2, expire_at=datetime(2026, 10, 24, tzinfo=UTC)),
        make_dict(3, expire_at=datetime(2026, 10, 26, tzinfo=UTC)),
    ]
    assert sorted_ids(cards) == [2, 3, 1]


def test_b2_null_expire_at_last():
    cards = [
        make_dict(1, expire_at=None),
        make_dict(2, expire_at=datetime(2026, 10, 24, tzinfo=UTC)),
    ]
    assert sorted_ids(cards) == [2, 1]


def test_b3_remaining_credits_ascending_within_same_expire():
    expire = datetime(2026, 10, 24, 23, 59, 59, tzinfo=UTC)
    cards = [
        make_dict(1, expire_at=expire, remaining_credits=5),
        make_dict(2, expire_at=expire, remaining_credits=1),
        make_dict(3, expire_at=expire, remaining_credits=3),
    ]
    assert sorted_ids(cards) == [2, 3, 1]


def test_b4_created_at_then_id_breaks_ties():
    expire = datetime(2026, 10, 24, tzinfo=UTC)
    cards = [
        make_dict(
            2, expire_at=expire, remaining_credits=1,
            created_at=datetime(2026, 2, 1, tzinfo=UTC),
        ),
        make_dict(
            1, expire_at=expire, remaining_credits=1,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        make_dict(
            3, expire_at=expire, remaining_credits=1,
            created_at=datetime(2026, 2, 1, tzinfo=UTC),
        ),
    ]
    assert sorted_ids(cards) == [1, 2, 3]


def test_b5_count_card_before_no_remaining_card_on_same_expire():
    expire = datetime(2026, 10, 24, tzinfo=UTC)
    cards = [
        make_dict(
            1, card_type=CardType.PERIOD.value, remaining_credits=None,
            expire_at=expire, created_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        make_dict(
            2, card_type=CardType.UNLIMITED.value, remaining_credits=None,
            expire_at=expire, created_at=datetime(2026, 1, 2, tzinfo=UTC),
        ),
        make_dict(
            3, remaining_credits=2, expire_at=expire,
            created_at=datetime(2026, 1, 3, tzinfo=UTC),
        ),
    ]
    assert sorted_ids(cards) == [3, 1, 2]


# ============================================================
# B-6 / B-7 / B-8 / D-7：共享不可用原因
# ============================================================


def _reason(card) -> str | None:
    return service.card_unavailable_reason(
        card,
        schedule_start_at=SCHEDULE_START,
        course_id=COURSE_ID,
        course_type_code=COURSE_TYPE,
    )


def test_b6_status_exclusions_have_distinct_reasons():
    assert _reason(make_card(status=CardStatus.EXPIRED.value)) == "已过期"
    assert _reason(make_card(status=CardStatus.FROZEN.value)) == "已冻结"
    assert _reason(make_card(status=CardStatus.CANCELLED.value)) == "已作废"
    assert _reason(make_card(status=CardStatus.PENDING.value)) == "未激活"
    assert (
        _reason(make_card(card_type=CardType.PERIOD.value,
                           status=CardStatus.FROZEN.value))
        == "已冻结"
    )


def test_b6_valid_from_exclusion():
    reason = _reason(make_card(valid_from=datetime(2026, 10, 23, tzinfo=UTC)))
    assert reason == "尚未生效（2026-10-23 生效）"


def test_b6_expire_at_exclusion():
    reason = _reason(make_card(expire_at=datetime(2026, 10, 21, tzinfo=UTC)))
    assert reason == "已过期（2026-10-21 到期）"


def test_b6_course_type_and_course_exclusions():
    assert (
        _reason(make_card(applicable_course_type_code="other"))
        == "不适用于此课程类型"
    )
    # 排期无课程类型时，限定类型的卡同样不适用
    assert (
        service.card_unavailable_reason(
            make_card(applicable_course_type_code=COURSE_TYPE),
            schedule_start_at=SCHEDULE_START,
            course_id=COURSE_ID,
            course_type_code=None,
        )
        == "不适用于此课程类型"
    )
    assert (
        _reason(make_card(applicable_course_ids=[COURSE_ID + 1]))
        == "不适用于此课程"
    )
    assert _reason(make_card(applicable_course_ids=[COURSE_ID])) is None
    assert _reason(make_card(applicable_course_type_code=COURSE_TYPE)) is None


def test_b6_count_card_used_up_excluded_only_in_recommendation_chain():
    card = make_dict(1, remaining_credits=0)
    # 共享判定不含余额规则（与下单校验保持同构）
    assert _reason(card) is None
    reason = service.card_recommend_unavailable_reason(
        card,
        schedule_start_at=SCHEDULE_START,
        course_id=COURSE_ID,
        course_type_code=COURSE_TYPE,
    )
    assert reason == "次卡已用完"


def test_b7_pending_period_card_without_valid_from_is_available():
    card = make_card(
        card_type=CardType.PERIOD.value,
        status=CardStatus.PENDING.value,
        total_credits=None,
        valid_from=None,
    )
    assert _reason(card) is None
    assert service.is_bookable_card(
        card,
        schedule_start_at=SCHEDULE_START,
        course_id=COURSE_ID,
        course_type_code=COURSE_TYPE,
    ) is True


def test_b8_pending_period_card_with_valid_from_is_unavailable():
    card = make_card(
        card_type=CardType.PERIOD.value,
        status=CardStatus.PENDING.value,
        total_credits=None,
        valid_from=datetime(2026, 10, 1, tzinfo=UTC),
    )
    assert _reason(card) == "未激活"
    assert service.is_bookable_card(
        card,
        schedule_start_at=SCHEDULE_START,
        course_id=COURSE_ID,
        course_type_code=COURSE_TYPE,
    ) is False


def test_b9_expire_at_same_day_available_next_day_unavailable():
    card = make_card(expire_at=datetime(2026, 10, 22, 23, 59, 59, tzinfo=UTC))
    assert _reason(card) is None

    next_day = SCHEDULE_START.replace(day=23)
    assert (
        service.card_unavailable_reason(
            card,
            schedule_start_at=next_day,
            course_id=COURSE_ID,
            course_type_code=COURSE_TYPE,
        )
        == "已过期（2026-10-22 到期）"
    )


def test_d7_unknown_card_type_is_excluded_even_when_active():
    card = make_dict(1, card_type="vip")
    assert _reason(card) == "不支持的卡类型"

    orm_card = make_card(card_type="vip", status=CardStatus.ACTIVE.value)
    assert (
        service.card_unavailable_reason(
            orm_card,
            schedule_start_at=SCHEDULE_START,
            course_id=COURSE_ID,
            course_type_code=COURSE_TYPE,
        )
        == "不支持的卡类型"
    )
    assert service.is_bookable_card(
        orm_card,
        schedule_start_at=SCHEDULE_START,
        course_id=COURSE_ID,
        course_type_code=COURSE_TYPE,
    ) is False


def test_is_bookable_card_delegates_shared_reason():
    usable = make_card(expire_at=datetime(2026, 10, 25, tzinfo=UTC))
    unusable_cases = [
        make_card(status=CardStatus.EXPIRED.value),
        make_card(valid_from=datetime(2026, 10, 23, tzinfo=UTC)),
        make_card(applicable_course_type_code="other"),
    ]
    assert service.is_bookable_card(
        usable,
        schedule_start_at=SCHEDULE_START,
        course_id=COURSE_ID,
        course_type_code=COURSE_TYPE,
    ) is True
    for card in unusable_cases:
        assert service.is_bookable_card(
            card,
            schedule_start_at=SCHEDULE_START,
            course_id=COURSE_ID,
            course_type_code=COURSE_TYPE,
        ) is False


# ============================================================
# B-10：空态文案聚合
# ============================================================


def test_b10_message_without_cards():
    assert service._recommend_message(0, 0, []) == "您还没有会员卡"


def test_b10_message_aggregates_deduplicated_reasons():
    message = service._recommend_message(
        3, 0, ["已过期（2026-10-21 到期）", "已冻结", "已过期（2026-10-21 到期）"]
    )
    assert message == "暂无可用会员卡：已过期（2026-10-21 到期）；已冻结"


def test_b10_message_none_when_available():
    assert service._recommend_message(2, 1, ["已冻结"]) is None
