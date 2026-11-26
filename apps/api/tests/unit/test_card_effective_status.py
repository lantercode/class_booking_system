"""P3-0 会员卡有效状态纯派生边界测试。

derive_card_effective_status 不查 DB / 不读 config，
全部场景靠 now 精确控制；CANCELLED / FROZEN / EXPIRED / ACTIVE / PENDING 五态覆盖。
"""

from datetime import UTC, datetime, timedelta

from app.modules.membership.models import CardStatus
from app.modules.membership.service import derive_card_effective_status


def _now(**overrides) -> datetime:
    """固定 now 便于断言；overrides 可加 seconds/minutes/hours 微调。"""
    return datetime(2026, 11, 24, 12, 0, 0, tzinfo=UTC) + timedelta(**overrides)


# ============================================================
# 业务语义：CANCELLED 永远是 CANCELLED，时间无关
# ============================================================


def test_cancelled_always_cancelled_even_past_expire():
    now = _now()
    assert derive_card_effective_status(
        db_status=CardStatus.CANCELLED.value,
        valid_from=None,
        expire_at=now - timedelta(days=30),
        frozen_until=None,
        now=now,
    ) == CardStatus.CANCELLED.value


# ============================================================
# ACTIVE + expire_at <= now → EXPIRED（脏数据：scheduler 还没跑）
# ============================================================


def test_active_card_with_past_expire_is_expired():
    now = _now()
    assert derive_card_effective_status(
        db_status=CardStatus.ACTIVE.value,
        valid_from=now - timedelta(days=90),
        expire_at=now - timedelta(minutes=5),
        frozen_until=None,
        now=now,
    ) == CardStatus.EXPIRED.value


def test_active_card_future_expire_stays_active():
    now = _now()
    assert derive_card_effective_status(
        db_status=CardStatus.ACTIVE.value,
        valid_from=now - timedelta(days=30),
        expire_at=now + timedelta(days=60),
        frozen_until=None,
        now=now,
    ) == CardStatus.ACTIVE.value


def test_exact_expire_boundary():
    """expire_at == now：左闭右开，应该算过期。"""
    now = _now()
    assert derive_card_effective_status(
        db_status=CardStatus.ACTIVE.value,
        valid_from=now - timedelta(days=30),
        expire_at=now,
        frozen_until=None,
        now=now,
    ) == CardStatus.EXPIRED.value


# ============================================================
# FROZEN 的两种情况：冻结中 vs 冻结到期自动解冻
# ============================================================


def test_frozen_inside_freeze_window_stays_frozen():
    now = _now()
    assert derive_card_effective_status(
        db_status=CardStatus.FROZEN.value,
        valid_from=now - timedelta(days=30),
        expire_at=now + timedelta(days=60),
        frozen_until=now + timedelta(days=7),
        now=now,
    ) == CardStatus.FROZEN.value


def test_frozen_after_frozen_until_unfreezes_and_moves_to_expired_if_due():
    """冻结到期自动解冻，但解冻后发现 expire_at 也过了——走过期优先。"""
    now = _now()
    assert derive_card_effective_status(
        db_status=CardStatus.FROZEN.value,
        valid_from=now - timedelta(days=30),
        expire_at=now - timedelta(minutes=5),
        frozen_until=now - timedelta(hours=1),
        now=now,
    ) == CardStatus.EXPIRED.value


def test_frozen_after_frozen_until_unfreezes_to_active():
    """冻结到期自动解冻，解冻后 expire_at 还没到。"""
    now = _now()
    assert derive_card_effective_status(
        db_status=CardStatus.FROZEN.value,
        valid_from=now - timedelta(days=30),
        expire_at=now + timedelta(days=60),
        frozen_until=now - timedelta(hours=1),
        now=now,
    ) == CardStatus.ACTIVE.value


def test_frozen_until_none_is_treated_as_frozen_forever():
    """历史脏数据：status=FROZEN 但 frozen_until 为空——当冻结中处理。"""
    now = _now()
    assert derive_card_effective_status(
        db_status=CardStatus.FROZEN.value,
        valid_from=now - timedelta(days=30),
        expire_at=now + timedelta(days=60),
        frozen_until=None,
        now=now,
    ) == CardStatus.FROZEN.value


# ============================================================
# PENDING 的三种情况：未到生效 / 该激活 / 已过期
# ============================================================


def test_pending_with_future_valid_from_stays_pending():
    now = _now()
    assert derive_card_effective_status(
        db_status=CardStatus.PENDING.value,
        valid_from=now + timedelta(days=7),
        expire_at=now + timedelta(days=90),
        frozen_until=None,
        now=now,
    ) == CardStatus.PENDING.value


def test_pending_with_past_valid_from_becomes_active():
    """valid_from 已过但 scheduler auto_activate 还没跑——读起来应该是 ACTIVE。"""
    now = _now()
    assert derive_card_effective_status(
        db_status=CardStatus.PENDING.value,
        valid_from=now - timedelta(days=7),
        expire_at=now + timedelta(days=83),
        frozen_until=None,
        now=now,
    ) == CardStatus.ACTIVE.value


def test_pending_past_expire_goes_expired_even_if_valid_from_none():
    """带 expire_at 的历史 PENDING 卡过了有效期——必须是 EXPIRED。"""
    now = _now()
    assert derive_card_effective_status(
        db_status=CardStatus.PENDING.value,
        valid_from=None,
        expire_at=now - timedelta(days=1),
        frozen_until=None,
        now=now,
    ) == CardStatus.EXPIRED.value


# ============================================================
# 空 expire_at：无限卡不过期，不派生
# ============================================================


def test_active_without_expire_stays_active():
    now = _now()
    assert derive_card_effective_status(
        db_status=CardStatus.ACTIVE.value,
        valid_from=now - timedelta(days=30),
        expire_at=None,
        frozen_until=None,
        now=now,
    ) == CardStatus.ACTIVE.value


# ============================================================
# db_status=EXPIRED 确认不被时间反向激活
# ============================================================


def test_expired_stays_expired_even_before_expire_at():
    """业务已标记 EXPIRED（可能是手动作废或历史 bug），不管时间如何都保持 EXPIRED。"""
    now = _now()
    assert derive_card_effective_status(
        db_status=CardStatus.EXPIRED.value,
        valid_from=None,
        expire_at=now + timedelta(days=30),
        frozen_until=None,
        now=now,
    ) == CardStatus.EXPIRED.value
