"""F4.3 解冻批量操作锁排序 - 单元测试

验证目标（对应 Feature 4.3 Acceptance Criteria）：
- AC-1：unfreeze_and_cancel_conflicts 接收无序 conflict_card_ids 时按 sorted 顺序加锁
- AC-2：unfreeze_and_freeze_conflicts 同上
- AC-3：batch_cancel_cards 接收无序 card_ids 时按 sorted 顺序加锁（扩展修复）
- AC-4：空列表不报错（主卡仍解冻，无 conflict 加锁调用）
- AC-5：单元素列表不报错，加锁顺序 == [主卡, 单元素]

测试方法：
  monkeypatch spy 替换 MembershipCardService.get_card_with_lock，
  记录 card_id 调用顺序，断言 == sorted(...)。
  用 SimpleNamespace + AsyncMock/MagicMock 构造 FakeCard 与 mock db，
  不依赖真 DB / Redis（conftest autouse session fixture 仍跑，dev 环境可用）。

死锁预防等价证明（AC-6）：
  spy 证明"所有请求加锁顺序收敛到 sorted(set) 全局升序"是 Coffman
  死锁"循环等待"条件被打破的充分条件 → 死锁不可能。
  真实双连接反序死锁复现见 runtime-test-report.md §6（不在测试基建内）。

运行方式：
    cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_unfreeze_lock_ordering.py -v
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.modules.membership.models import CardStatus
from app.modules.membership.service import MembershipCardService

MAIN_CARD_ID = 100  # 主卡 ID（被解冻的卡）
TENANT_ID = 1
OPERATOR_ID = 1


# ============================================================
# Fake 工厂
# ============================================================


def _make_main_card():
    """构造主卡 FakeCard：status=FROZEN，有 frozen_remaining_days（触发重算 expire_at）"""
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=MAIN_CARD_ID,
        tenant_id=TENANT_ID,
        status=CardStatus.FROZEN.value,
        student_id=1,
        total_credits=10,
        used_credits=3,
        frozen_remaining_days=10,
        frozen_reason="原冻结原因",
        frozen_at=now - timedelta(days=5),
        frozen_until=now + timedelta(days=5),
        expire_at=now + timedelta(days=30),
        cancelled_at=None,
        cancelled_reason=None,
    )


def _make_conflict_card(card_id, status=CardStatus.ACTIVE.value):
    """构造 conflict 卡 FakeCard（与主卡同 student_id=1）"""
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=card_id,
        tenant_id=TENANT_ID,
        status=status,
        student_id=1,  # 与主卡同学生
        total_credits=10,
        used_credits=3,  # remaining=7>0 触发流水
        frozen_remaining_days=None,
        frozen_reason=None,
        frozen_at=None,
        frozen_until=None,
        expire_at=now + timedelta(days=30),  # freeze 路径需要 expire_at 计算 remaining_days
        cancelled_at=None,
        cancelled_reason=None,
    )


def _make_db():
    """构造 mock AsyncSession：add 同步，flush/refresh/commit async"""
    return SimpleNamespace(
        add=MagicMock(),
        flush=AsyncMock(),
        refresh=AsyncMock(),
        commit=AsyncMock(),
    )


def _install_spy(service, main_card, conflict_cards_by_id):
    """替换 service.get_card_with_lock 为 spy，返回 calls 列表

    实例属性覆盖类方法，调用 self.get_card_with_lock(db, card_id, tenant_id)
    时不绑定 self（普通函数赋值），参数 db/card_id/tenant_id 正好匹配。
    """

    calls = []

    async def spy(db, card_id, tenant_id):
        calls.append(card_id)
        if main_card is not None and card_id == main_card.id:
            return main_card
        return conflict_cards_by_id[card_id]

    service.get_card_with_lock = spy
    return calls


def _mock_freeze_repo(service):
    """mock freeze_repo.list_freezes 返回 ([], 0)（避免真 DB）"""
    service.freeze_repo = SimpleNamespace(list_freezes=AsyncMock(return_value=([], 0)))


# ============================================================
# AC-1：unfreeze_and_cancel_conflicts 排序加锁
# ============================================================


async def test_unfreeze_and_cancel_sorts_conflict_ids():
    """AC-1：传入无序 [3,1,2]，spy 调用顺序 == [主卡, 1, 2, 3]"""
    service = MembershipCardService()
    main_card = _make_main_card()
    conflict_ids = [3, 1, 2]
    conflict_cards = {cid: _make_conflict_card(cid) for cid in conflict_ids}
    calls = _install_spy(service, main_card, conflict_cards)
    _mock_freeze_repo(service)
    db = _make_db()

    result = await service.unfreeze_and_cancel_conflicts(
        db, MAIN_CARD_ID, TENANT_ID, OPERATOR_ID, conflict_ids, "测试作废"
    )

    # 主卡调用在前（L895），conflict 卡按 sorted 升序
    assert calls == [MAIN_CARD_ID, 1, 2, 3]
    assert result["success_count"] == 3
    assert result["failed_cards"] == []
    assert len(result["cancelled_cards"]) == 3


# ============================================================
# AC-2：unfreeze_and_freeze_conflicts 排序加锁
# ============================================================


async def test_unfreeze_and_freeze_sorts_conflict_ids():
    """AC-2：传入无序 [3,1,2]，spy 调用顺序 == [主卡, 1, 2, 3]"""
    service = MembershipCardService()
    main_card = _make_main_card()
    conflict_ids = [3, 1, 2]
    conflict_cards = {cid: _make_conflict_card(cid) for cid in conflict_ids}
    calls = _install_spy(service, main_card, conflict_cards)
    _mock_freeze_repo(service)
    db = _make_db()

    result = await service.unfreeze_and_freeze_conflicts(
        db, MAIN_CARD_ID, TENANT_ID, OPERATOR_ID, conflict_ids, "测试冻结", 365
    )

    assert calls == [MAIN_CARD_ID, 1, 2, 3]
    assert result["success_count"] == 3
    assert result["failed_cards"] == []
    assert len(result["frozen_cards"]) == 3


# ============================================================
# AC-3：batch_cancel_cards 排序加锁（扩展修复）
# ============================================================


async def test_batch_cancel_sorts_card_ids():
    """AC-3：传入无序 [3,1,2]，spy 调用顺序 == [1,2,3]（无主卡前缀）"""
    service = MembershipCardService()
    card_ids = [3, 1, 2]
    # batch_cancel 内部调 cancel_card，cancel_card 内 get_card_with_lock
    # 需返回非 CANCELLED 的卡（status=ACTIVE）让流程走完
    cards_by_id = {cid: _make_conflict_card(cid, status=CardStatus.ACTIVE.value) for cid in card_ids}
    calls = _install_spy(service, main_card=None, conflict_cards_by_id=cards_by_id)
    db = _make_db()

    result = await service.batch_cancel_cards(db, card_ids, TENANT_ID, "批量作废", OPERATOR_ID)

    # 无主卡前缀，纯循环按 sorted 升序
    assert calls == [1, 2, 3]
    assert result["success_count"] == 3
    assert result["failed_count"] == 0
    assert result["total"] == 3


# ============================================================
# AC-4：空列表不报错
# ============================================================


async def test_unfreeze_and_cancel_empty_list_safe():
    """AC-4：空 conflict_card_ids=[]，主卡仍解冻，不报错"""
    service = MembershipCardService()
    main_card = _make_main_card()
    calls = _install_spy(service, main_card, {})
    _mock_freeze_repo(service)
    db = _make_db()

    result = await service.unfreeze_and_cancel_conflicts(
        db, MAIN_CARD_ID, TENANT_ID, OPERATOR_ID, [], "测试作废"
    )

    # 只调用主卡（L895），循环不执行
    assert calls == [MAIN_CARD_ID]
    assert result["success_count"] == 0
    assert result["cancelled_cards"] == []
    assert result["failed_cards"] == []


async def test_unfreeze_and_freeze_empty_list_safe():
    """AC-4：空 conflict_card_ids=[]，主卡仍解冻，不报错"""
    service = MembershipCardService()
    main_card = _make_main_card()
    calls = _install_spy(service, main_card, {})
    _mock_freeze_repo(service)
    db = _make_db()

    result = await service.unfreeze_and_freeze_conflicts(
        db, MAIN_CARD_ID, TENANT_ID, OPERATOR_ID, [], "测试冻结", 365
    )

    assert calls == [MAIN_CARD_ID]
    assert result["success_count"] == 0
    assert result["frozen_cards"] == []
    assert result["failed_cards"] == []


# ============================================================
# AC-5：单元素列表不报错
# ============================================================


async def test_unfreeze_and_cancel_single_element_safe():
    """AC-5：单元素 [5]，spy 调用顺序 == [主卡, 5]，success_count==1"""
    service = MembershipCardService()
    main_card = _make_main_card()
    conflict_cards = {5: _make_conflict_card(5)}
    calls = _install_spy(service, main_card, conflict_cards)
    _mock_freeze_repo(service)
    db = _make_db()

    result = await service.unfreeze_and_cancel_conflicts(
        db, MAIN_CARD_ID, TENANT_ID, OPERATOR_ID, [5], "测试作废"
    )

    assert calls == [MAIN_CARD_ID, 5]
    assert result["success_count"] == 1
    assert len(result["cancelled_cards"]) == 1


async def test_unfreeze_and_freeze_single_element_safe():
    """AC-5：单元素 [5]（freeze 路径），spy 调用顺序 == [主卡, 5]"""
    service = MembershipCardService()
    main_card = _make_main_card()
    conflict_cards = {5: _make_conflict_card(5)}
    calls = _install_spy(service, main_card, conflict_cards)
    _mock_freeze_repo(service)
    db = _make_db()

    result = await service.unfreeze_and_freeze_conflicts(
        db, MAIN_CARD_ID, TENANT_ID, OPERATOR_ID, [5], "测试冻结", 365
    )

    assert calls == [MAIN_CARD_ID, 5]
    assert result["success_count"] == 1
    assert len(result["frozen_cards"]) == 1


# ============================================================
# AC-6：并发死锁预防（spy 等价证明）
# ============================================================


async def test_concurrent_callers_converge_to_global_order():
    """AC-6：两个反序请求经 sorted 后加锁顺序一致 → 无循环等待

    模拟 T1 传 [3,1,2]、T2 传 [1,2,3]，分别 spy 后断言两者 calls[1:]
    均为 [1,2,3] → 所有并发请求加锁顺序收敛到 sorted(set) 全局升序 →
    Coffman 循环等待条件被打破 → 死锁不可能。
    """
    service1 = MembershipCardService()
    main_card1 = _make_main_card()
    cards1 = {cid: _make_conflict_card(cid) for cid in [1, 2, 3]}
    calls1 = _install_spy(service1, main_card1, cards1)
    _mock_freeze_repo(service1)
    await service1.unfreeze_and_cancel_conflicts(
        _make_db(), MAIN_CARD_ID, TENANT_ID, OPERATOR_ID, [3, 1, 2], "T1"
    )

    service2 = MembershipCardService()
    main_card2 = _make_main_card()
    cards2 = {cid: _make_conflict_card(cid) for cid in [1, 2, 3]}
    calls2 = _install_spy(service2, main_card2, cards2)
    _mock_freeze_repo(service2)
    await service2.unfreeze_and_cancel_conflicts(
        _make_db(), MAIN_CARD_ID, TENANT_ID, OPERATOR_ID, [1, 2, 3], "T2"
    )

    # 两个请求的 conflict 加锁顺序均 == [1,2,3]（去掉主卡前缀）
    assert calls1[1:] == [1, 2, 3]
    assert calls2[1:] == [1, 2, 3]
    # 全局升序收敛 → 不存在持有 A 等 B 与持有 B 等 A 的对峙 → 无死锁
