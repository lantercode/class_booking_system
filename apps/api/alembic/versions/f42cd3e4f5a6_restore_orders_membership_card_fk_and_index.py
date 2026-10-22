"""restore_orders_membership_card_fk_and_index

恢复 orders.membership_card_id -> membership_cards.id 外键约束
（ON DELETE SET NULL）并新增该列索引。

背景：orders 表在 `57aeb9dcf020_add_membership_card_id_to_orders_table`
新增 membership_card_id 列时仅落库 BigInteger，未带外键；Order ORM 模型
亦无 ForeignKey。本 migration 在同一事务内：
  1. 清理孤立引用（membership_card_id 指向不存在的卡）置 NULL；
  2. 重建外键 fk_orders_membership_card_id（ON DELETE SET NULL）；
  3. 新增索引 ix_orders_membership_card_id（加速 ON DELETE SET NULL
     时的引用行定位，并为按卡查询订单提供索引支撑）。

Revision ID: f42cd3e4f5a6
Revises: f41ab2c3d4e5
Create Date: 2026-09-29

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f42cd3e4f5a6"
down_revision: str | Sequence[str] | None = "f41ab2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# 约束名（与 Order 模型 ForeignKey 一致，便于 downgrade 精确 drop）
FK_NAME = "fk_orders_membership_card_id"
# 索引名（与 Order 模型 Index 定义一致）
INDEX_NAME = "ix_orders_membership_card_id"


def upgrade() -> None:
    """Upgrade schema.

    步骤（同一事务内，原子完成）：
      1. 清理孤立引用：把 membership_card_id 指向不存在 membership_cards.id
         的 order 行的 membership_card_id 置为 NULL。
      2. 重建外键：orders.membership_card_id -> membership_cards.id
         ON DELETE SET NULL。
      3. 新增索引：ix_orders_membership_card_id（加速 ON DELETE SET NULL
         时的引用行定位 + 按卡查订单）。
    """
    # 1. 清理孤立数据（T4.2.1 前置）
    #    NOT IN 子查询处理 membership_cards.id 列；NULL membership_card_id
    #    行不受影响（WHERE membership_card_id IS NOT NULL）。
    op.execute(
        sa.text(
            """
            UPDATE orders
               SET membership_card_id = NULL
             WHERE membership_card_id IS NOT NULL
               AND membership_card_id NOT IN (SELECT id FROM membership_cards)
            """
        )
    )

    # 2. 加外键约束（T4.2.1）
    op.create_foreign_key(
        constraint_name=FK_NAME,
        source_table="orders",
        referent_table="membership_cards",
        local_cols=["membership_card_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )

    # 3. 加索引（T4.2.2）
    op.create_index(
        index_name=INDEX_NAME,
        table_name="orders",
        columns=["membership_card_id"],
    )


def downgrade() -> None:
    """Downgrade schema.

    顺序与 upgrade 相反：先 drop 索引再 drop 外键（避免 drop 外键时
    触发依赖索引的副作用）；不恢复孤立数据（原始指向的卡本就不存在，
    无可恢复信息）。
    """
    op.drop_index(
        index_name=INDEX_NAME,
        table_name="orders",
    )

    op.drop_constraint(
        constraint_name=FK_NAME,
        table_name="orders",
        type_="foreignkey",
    )
