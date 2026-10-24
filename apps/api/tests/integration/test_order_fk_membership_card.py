"""
F4.2 恢复 orders.membership_card_id 外键 + 索引 - 集成测试

验证目标（对应 Feature 4.2 Acceptance Criteria）：
- AC-1：FK 约束 fk_orders_membership_card_id 存在且 ON DELETE SET NULL
- AC-2：索引 ix_orders_membership_card_id 存在
- AC-3：创建 order 引用存在的卡 → 成功（membership_card_id 落库）
- AC-4：创建 order 引用不存在的 card_id → IntegrityError（FK 校验）
- AC-5：删除 card → 关联 order.membership_card_id 变 NULL（ON DELETE SET NULL）
- AC-6：migration 已清理孤立数据（孤立计数 == 0）
- AC-7：migration 清理逻辑本身正确（drop FK → 插孤立 → 清理 UPDATE →
        card_id 变 NULL → re-add FK 成功；全程事务回滚不污染 DB）

事务/隔离设计（借鉴 F4.1 / F2.4）：
  - shared_data（session-scoped）在 session loop 内 dispose engine，只返回纯数据 dict。
  - local_db（function-scoped）为每用例独立 engine + session_factory。
  - AC-7 在一个显式事务内 drop FK / 插孤立 / 清理 / re-add FK，最终 rollback；
    PostgreSQL DDL 事务化，rollback 还原原状，不污染 dev DB。

前置条件：
  - migration f42cd3e4f5a6 已 apply（alembic_version == f42cd3e4f5a6）
  - 种子数据已由 conftest.seed_test_database 初始化
    （super_admin=13800000001 / teacher=13800138001 / student=13900139001，密码 Test@123456）

运行方式：
    cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_order_fk_membership_card.py -v
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.tenant_context import set_tenant_id
from app.modules.membership.models import CardStatus, MembershipCard
from app.modules.order.models import ItemType, Order, OrderStatus
from app.modules.tenant.models import Tenant
from app.modules.user.models import User

TENANT_SLUG = "dance-school"
SEED_STUDENT_PHONE = "13900139001"
SEED_TEACHER_PHONE = "13800138001"
SEED_ADMIN_PHONE = "13800000001"
NONEXISTENT_CARD_ID = 999_999_999  # 不存在的会员卡 ID（FK 校验用）

FK_NAME = "fk_orders_membership_card_id"
INDEX_NAME = "ix_orders_membership_card_id"


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture(scope="session")
async def shared_data():
    """session-scoped：解析种子 IDs，返回纯数据 dict。

    engine 在本 fixture 内创建并 dispose，只返回纯数据 dict——避免 session
    loop 的 engine 被后续 function-scoped 用例跨 loop 复用。
    """
    settings = get_settings()
    engine = create_async_engine(
        settings.DATABASE_URL, echo=False, pool_size=3, max_overflow=5, pool_pre_ping=True
    )
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    tenant_id: int
    student_id: int
    teacher_id: int
    admin_id: int

    async with session_factory() as session:
        tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == TENANT_SLUG))
        ).scalar_one()
        tenant_id = tenant.id
        student_id = (
            await session.execute(select(User).where(User.phone == SEED_STUDENT_PHONE))
        ).scalar_one().id
        teacher_id = (
            await session.execute(select(User).where(User.phone == SEED_TEACHER_PHONE))
        ).scalar_one().id
        admin_id = (
            await session.execute(select(User).where(User.phone == SEED_ADMIN_PHONE))
        ).scalar_one().id

    data = {
        "tenant_id": tenant_id,
        "student_id": student_id,
        "teacher_id": teacher_id,
        "admin_id": admin_id,
    }
    yield data

    # 兜底清理：可能残留的测试 order / card（各用例正常应自行清理）
    async with session_factory() as session:
        set_tenant_id(data["tenant_id"])
        # 清理本测试可能残留的 order（按 tenant + item_type='card' 桶 + 非种子 order_no）
        await session.execute(
            delete(Order).where(
                Order.tenant_id == data["tenant_id"],
                Order.item_type == ItemType.CARD.value,
            ).where(
                # 只清理测试写入的 order（order_no 以 "TEST-" 开头）
                text("order_no LIKE 'TEST-%'")
            )
        )
        # 清理可能残留的测试 card
        await session.execute(
            text(
                "DELETE FROM membership_card_transactions WHERE card_id IN ("
                "SELECT id FROM membership_cards WHERE card_no LIKE 'TEST-%')"
            )
        )
        await session.execute(
            delete(MembershipCard).where(MembershipCard.card_no.like("TEST-%"))
        )
        await session.commit()
    await engine.dispose()


@pytest.fixture(scope="function")
async def local_db():
    """function-scoped engine + session_factory，绑定当前用例事件循环。"""
    settings = get_settings()
    engine = create_async_engine(
        settings.DATABASE_URL, echo=False, pool_size=2, max_overflow=3, pool_pre_ping=True
    )
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    yield session_factory
    await engine.dispose()


# ============================================================
# Helper：直接落库构造 card / order 数据
# ============================================================


def _gen_order_no() -> str:
    """生成 32 字符内的唯一 order_no（TEST- 前缀便于兜底清理识别）。"""
    return f"TEST-{uuid4().hex[:26]}"  # 5 + 26 = 31 字符，<= 32


def _gen_card_no() -> str:
    """生成测试用 card_no（TEST- 前缀便于兜底清理识别）。"""
    # MembershipCard.card_no 限长 17；用 TEST- + 12 随机
    return f"TEST-{uuid4().hex[:12]}"


async def _create_card(sf, data: dict, student_id: int) -> int:
    """直接落库 1 个 ACTIVE 会员卡，返回 id（调用方负责清理）。"""
    async with sf() as session:
        set_tenant_id(data["tenant_id"])
        card = MembershipCard(
            tenant_id=data["tenant_id"],
            student_id=student_id,
            card_type="count",
            card_no=_gen_card_no(),
            total_credits=10,
            used_credits=0,
            valid_from=datetime.now(UTC) - timedelta(days=1),
            expire_at=datetime.now(UTC) + timedelta(days=30),
            status=CardStatus.ACTIVE.value,
        )
        session.add(card)
        await session.flush()
        card_id = card.id
        await session.commit()
    return card_id


async def _create_order(
    sf,
    data: dict,
    user_id: int,
    *,
    card_id: int | None = None,
    status: int = OrderStatus.PENDING.value,
) -> int:
    """直接落库 1 个 order，返回 id（调用方负责清理）。

    item_id 用 1（无 FK 约束的占位值）；item_type='card'；amount=99.00。
    """
    async with sf() as session:
        set_tenant_id(data["tenant_id"])
        order = Order(
            tenant_id=data["tenant_id"],
            user_id=user_id,
            order_no=_gen_order_no(),
            item_type=ItemType.CARD.value,
            item_id=1,
            amount=Decimal("99.00"),
            status=status,
            membership_card_id=card_id,
        )
        session.add(order)
        await session.flush()
        order_id = order.id
        await session.commit()
    return order_id


async def _cleanup(
    sf,
    data: dict,
    *,
    card_id: int | None = None,
    order_id: int | None = None,
) -> None:
    """按 id 清理测试数据；每步独立 session + commit，避免单步失败阻塞后续清理。

    顺序：先删 order（避免引用 card 时被 FK 阻塞——虽然 ON DELETE SET NULL
    不会阻塞，但保留语义清晰），再清理 card 的 txn 再删 card。
    """
    targets = [("order", order_id), ("card", card_id)]
    for kind, _id in targets:
        if _id is None:
            continue
        async with sf() as session:
            set_tenant_id(data["tenant_id"])
            if kind == "order":
                await session.execute(delete(Order).where(Order.id == _id))
            elif kind == "card":
                # 先删可能引用 card 的 txn，再删 card
                await session.execute(
                    text(
                        "DELETE FROM membership_card_transactions WHERE card_id = :cid"
                    ),
                    {"cid": _id},
                )
                await session.execute(
                    delete(MembershipCard).where(MembershipCard.id == _id)
                )
            await session.commit()


# ============================================================
# 测试用例
# ============================================================


class TestOrderFkMembershipCard:
    """F4.2 orders.membership_card_id 外键 + 索引行为验证。"""

    # AC-1：FK 约束存在且 ON DELETE SET NULL
    async def test_fk_constraint_exists_with_on_delete_set_null(self, local_db, shared_data):
        sf = local_db
        data = shared_data
        async with sf() as session:
            set_tenant_id(data["tenant_id"])
            conn = await session.connection()
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT pg_get_constraintdef(oid)
                          FROM pg_constraint
                         WHERE conrelid = 'orders'::regclass
                           AND conname = :name
                        """
                    ),
                    {"name": FK_NAME},
                )
            ).scalar_one_or_none()
            assert row is not None, f"FK {FK_NAME} 不存在"
            assert "FOREIGN KEY (membership_card_id) REFERENCES membership_cards(id)" in row
            assert "ON DELETE SET NULL" in row

    # AC-2：索引 ix_orders_membership_card_id 存在
    async def test_index_on_membership_card_id_exists(self, local_db, shared_data):
        sf = local_db
        data = shared_data
        async with sf() as session:
            set_tenant_id(data["tenant_id"])
            conn = await session.connection()
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT indexdef
                          FROM pg_indexes
                         WHERE tablename = 'orders'
                           AND indexname = :name
                        """
                    ),
                    {"name": INDEX_NAME},
                )
            ).scalar_one_or_none()
            assert row is not None, f"Index {INDEX_NAME} 不存在"
            assert "CREATE INDEX" in row
            assert "ix_orders_membership_card_id" in row
            assert "membership_card_id" in row

    # AC-3：正常 order 引用存在的卡 → 成功
    async def test_order_with_valid_membership_card_succeeds(self, local_db, shared_data):
        sf = local_db
        data = shared_data
        card_id = await _create_card(sf, data, data["student_id"])
        order_id: int | None = None
        try:
            order_id = await _create_order(
                sf, data, data["student_id"], card_id=card_id
            )
            # 重新读取确认 membership_card_id 落库
            async with sf() as session:
                set_tenant_id(data["tenant_id"])
                fetched = (
                    await session.execute(select(Order).where(Order.id == order_id))
                ).scalar_one()
                assert fetched.membership_card_id == card_id
        finally:
            await _cleanup(sf, data, card_id=card_id, order_id=order_id)

    # AC-4：order 引用不存在的 card_id → IntegrityError
    async def test_order_with_nonexistent_card_raises_integrity_error(
        self, local_db, shared_data
    ):
        sf = local_db
        data = shared_data
        async with sf() as session:
            set_tenant_id(data["tenant_id"])
            order = Order(
                tenant_id=data["tenant_id"],
                user_id=data["student_id"],
                order_no=_gen_order_no(),
                item_type=ItemType.CARD.value,
                item_id=1,
                amount=Decimal("99.00"),
                status=OrderStatus.PENDING.value,
                membership_card_id=NONEXISTENT_CARD_ID,
            )
            session.add(order)
            with pytest.raises(IntegrityError):
                await session.commit()
            # commit 失败后回滚，order 未落库
            await session.rollback()
        # 二次确认：引用该不存在 card_id 的 order 不存在
        async with sf() as session:
            set_tenant_id(data["tenant_id"])
            rows = (
                await session.execute(
                    select(Order).where(Order.membership_card_id == NONEXISTENT_CARD_ID)
                )
            ).scalars().all()
            assert rows == []

    # AC-5：删除 card → 关联 order.membership_card_id 变 NULL
    async def test_delete_card_sets_order_card_id_null(self, local_db, shared_data):
        sf = local_db
        data = shared_data
        card_id = await _create_card(sf, data, data["student_id"])
        order_id = await _create_order(
            sf, data, data["student_id"], card_id=card_id
        )
        try:
            # 删除 card（FK ON DELETE SET NULL 应把 order.membership_card_id 置 NULL）
            async with sf() as session:
                set_tenant_id(data["tenant_id"])
                await session.execute(
                    delete(MembershipCard).where(MembershipCard.id == card_id)
                )
                await session.commit()
            # 确认 order 仍存在且 membership_card_id 已被 SET NULL
            async with sf() as session:
                set_tenant_id(data["tenant_id"])
                fetched = (
                    await session.execute(select(Order).where(Order.id == order_id))
                ).scalar_one()
                assert fetched is not None
                assert fetched.membership_card_id is None
            card_id = None  # 已删，避免 cleanup 重复删除
        finally:
            await _cleanup(sf, data, card_id=card_id, order_id=order_id)

    # AC-6：migration 已清理孤立数据（孤立计数 == 0）
    async def test_no_orphan_orders_after_migration(self, local_db, shared_data):
        sf = local_db
        data = shared_data
        async with sf() as session:
            set_tenant_id(data["tenant_id"])
            conn = await session.connection()
            orphan_count = (
                await conn.execute(
                    text(
                        """
                        SELECT COUNT(*)
                          FROM orders o
                          LEFT JOIN membership_cards m ON o.membership_card_id = m.id
                         WHERE o.membership_card_id IS NOT NULL
                           AND m.id IS NULL
                        """
                    )
                )
            ).scalar()
            assert orphan_count == 0, f"migration 后仍存在 {orphan_count} 条孤立 order"


class TestOrderFkMigrationLogic:
    """F4.2 migration 清理逻辑本身正确（在事务内复刻，最终回滚不污染 DB）。

    复刻 migration upgrade 的三步：
      1. UPDATE 清理孤立引用
      2. ALTER TABLE ADD CONSTRAINT fk ... ON DELETE SET NULL
      3. CREATE INDEX ix_orders_membership_card_id

    为构造孤立引用，需先临时 DROP 约束（PostgreSQL DDL 事务化，
    整体 rollback 后还原原状）。索引不阻塞孤立插入，故测试不动索引。
    """

    async def test_migration_cleanup_clears_orphan_and_readds_fk(
        self, local_db, shared_data
    ):
        sf = local_db
        data = shared_data

        settings = get_settings()
        engine = create_async_engine(settings.DATABASE_URL, pool_size=2)
        order_id: int | None = None
        try:
            async with engine.connect() as conn:
                trans = await conn.begin()
                try:
                    # 1. 临时 drop FK（DDL 事务化，rollback 还原）
                    await conn.execute(
                        text(
                            f"ALTER TABLE orders DROP CONSTRAINT IF EXISTS {FK_NAME}"
                        )
                    )

                    # 2. 插入孤立 order（card_id 指向不存在的卡）
                    insert_sql = text(
                        """
                        INSERT INTO orders
                            (public_id, tenant_id, user_id, order_no,
                             item_type, item_id, amount, status,
                             membership_card_id)
                        VALUES
                            (:public_id, :tenant_id, :user_id, :order_no,
                             :item_type, :item_id, :amount, :status,
                             :card_id)
                        RETURNING id
                        """
                    )
                    result = await conn.execute(
                        insert_sql,
                        {
                            "public_id": str(uuid4()),
                            "tenant_id": data["tenant_id"],
                            "user_id": data["student_id"],
                            "order_no": _gen_order_no(),
                            "item_type": ItemType.CARD.value,
                            "item_id": 1,
                            "amount": Decimal("99.00"),
                            "status": OrderStatus.PENDING.value,
                            "card_id": NONEXISTENT_CARD_ID,
                        },
                    )
                    order_id = result.scalar()

                    # 3. 验证孤立引用已落库
                    pre = (
                        await conn.execute(
                            text(
                                "SELECT membership_card_id FROM orders WHERE id = :id"
                            ),
                            {"id": order_id},
                        )
                    ).scalar()
                    assert pre == NONEXISTENT_CARD_ID

                    # 4. 复刻 migration 的清理 UPDATE
                    await conn.execute(
                        text(
                            """
                            UPDATE orders
                               SET membership_card_id = NULL
                             WHERE membership_card_id IS NOT NULL
                               AND membership_card_id NOT IN (SELECT id FROM membership_cards)
                            """
                        )
                    )

                    # 5. 验证孤立引用被清理
                    post = (
                        await conn.execute(
                            text(
                                "SELECT membership_card_id FROM orders WHERE id = :id"
                            ),
                            {"id": order_id},
                        )
                    ).scalar()
                    assert post is None, "清理 UPDATE 未把孤立 membership_card_id 置 NULL"

                    # 6. 复刻 migration 的 re-add FK（清理后应成功）
                    await conn.execute(
                        text(
                            f"""
                            ALTER TABLE orders
                            ADD CONSTRAINT {FK_NAME}
                            FOREIGN KEY (membership_card_id)
                            REFERENCES membership_cards(id)
                            ON DELETE SET NULL
                            """
                        )
                    )
                finally:
                    # 整体回滚：DDL + DML 全部还原，dev DB 不受影响
                    await trans.rollback()
        finally:
            await engine.dispose()

        # 二次确认：rollback 后孤立 order 未落库（dev DB 无残留）
        async with sf() as session:
            set_tenant_id(data["tenant_id"])
            rows = (
                await session.execute(
                    select(Order).where(Order.id == (order_id or -1))
                )
            ).scalars().all()
            assert rows == [], "回滚后测试 order 不应残留"
