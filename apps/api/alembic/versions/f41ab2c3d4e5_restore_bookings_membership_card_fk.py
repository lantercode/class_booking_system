"""restore_bookings_membership_card_fk

恢复 bookings.membership_card_id -> membership_cards.id 外键约束
（ON DELETE SET NULL）。init_all_tables 原本定义了该 FK，后随模型
简化（仅留 BigInteger）丢失，DB 中该约束亦不存在；本 migration 在
恢复约束前先清理孤立引用（membership_card_id 指向不存在的卡），
再重建外键。

Revision ID: f41ab2c3d4e5
Revises: 211f847af16c
Create Date: 2026-09-29

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f41ab2c3d4e5"
down_revision: str | Sequence[str] | None = "211f847af16c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# 约束名（与 Booking 模型 ForeignKey 一致，便于 downgrade 精确 drop）
FK_NAME = "fk_bookings_membership_card_id"


def upgrade() -> None:
    """Upgrade schema.

    步骤（同一事务内，原子完成）：
      1. 清理孤立引用：把 membership_card_id 指向不存在 membership_cards.id
         的 booking 行的 membership_card_id 置为 NULL。
      2. 重建外键：bookings.membership_card_id -> membership_cards.id
         ON DELETE SET NULL。
    """
    # 1. 清理孤立数据（T4.1.1）
    #    NOT IN 子查询处理 membership_cards.id 列；NULL membership_card_id
    #    行不受影响（WHERE membership_card_id IS NOT NULL）。
    op.execute(
        sa.text(
            """
            UPDATE bookings
               SET membership_card_id = NULL
             WHERE membership_card_id IS NOT NULL
               AND membership_card_id NOT IN (SELECT id FROM membership_cards)
            """
        )
    )

    # 2. 加外键约束（T4.1.2）
    op.create_foreign_key(
        constraint_name=FK_NAME,
        source_table="bookings",
        referent_table="membership_cards",
        local_cols=["membership_card_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema.

    仅删除外键约束；已清理的孤立 membership_card_id 无法恢复
    （原始指向的卡本就不存在，无可恢复信息）。
    """
    op.drop_constraint(
        constraint_name=FK_NAME,
        table_name="bookings",
        type_="foreignkey",
    )
