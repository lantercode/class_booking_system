"""add_membership_card_validity_days

为 membership_cards 新增可空列 validity_days（发卡时确定的有效天数快照），
供 F6.3 期卡首次完成时按“发卡时的天数”计算有效期，避免产品配置变更
导致卡条款漂移。

upgrade（同一事务内，原子完成）：
  1. ADD COLUMN validity_days INTEGER NULL（不加 NOT NULL：存量数据可能无法回填；
     缺失时由 Service 层 fail-closed 处理）。
  2. 回填（仅处理 card_type='period' 且当前为 NULL 的行，可安全重复执行）：
     a. 优先从 membership_card_products.validity_days 读取（产品优先，见
        F6.3 implementation-plan UNKNOWN-3）；product_id 为空或产品天数为
        空/非正数时保持 NULL。
     b. 无产品天数时，用 expire_at/valid_from 的日期差反推（含首尾，
        即 (expire_at_date - valid_from_date) + 1）；日期倒挂等异常数据
        保持 NULL，不写入负值。
  3. 时间戳统一按 UTC 取日期（AT TIME ZONE 'UTC'），避免迁移会话 TimeZone
     影响回填结果；应用写入的 valid_from 为 00:00:00、expire_at 为
     23:59:59（见 MembershipCardService._calc_expire_at）。

downgrade：仅删除该列，不动任何业务数据。

说明：设计文档示例使用 SmallInteger，本迁移按任务约定与
membership_card_products.validity_days 保持一致使用 Integer，避免
跨列比较/回填时发生类型转换；取值范围不受影响。

Revision ID: a7b8c9d0e1f2
Revises: f44ab1c2d3e4
Create Date: 2026-10-22

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: str | Sequence[str] | None = "f44ab1c2d3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    步骤（同一事务内，原子完成）：
      1. 新增可空列 validity_days。
      2. 期卡回填：产品优先，其次按有效期日期差反推；无法解析保持 NULL。
         两条 UPDATE 均带 `validity_days IS NULL` 条件，重复执行不会覆盖
         已有值（幂等）。
    """
    # 1. 加列（T6.3.1 前置）
    op.add_column(
        "membership_cards",
        sa.Column(
            "validity_days",
            sa.Integer(),
            nullable=True,
            comment="发卡时确定的有效天数快照（期卡激活用）",
        ),
    )

    # 2a. 回填：产品优先（仅正数，避免 0/负数污染后续有效期计算）
    op.execute(
        sa.text(
            """
            UPDATE membership_cards AS c
               SET validity_days = p.validity_days
              FROM membership_card_products AS p
             WHERE c.product_id = p.id
               AND c.card_type = 'period'
               AND c.validity_days IS NULL
               AND p.validity_days IS NOT NULL
               AND p.validity_days > 0
            """
        )
    )

    # 2b. 回填：日期差反推（含首尾）；日期倒挂保持 NULL
    op.execute(
        sa.text(
            """
            UPDATE membership_cards
               SET validity_days = (
                       (expire_at AT TIME ZONE 'UTC')::date
                       - (valid_from AT TIME ZONE 'UTC')::date
                   ) + 1
             WHERE card_type = 'period'
               AND validity_days IS NULL
               AND valid_from IS NOT NULL
               AND expire_at IS NOT NULL
               AND (expire_at AT TIME ZONE 'UTC')::date
                   >= (valid_from AT TIME ZONE 'UTC')::date
            """
        )
    )


def downgrade() -> None:
    """Downgrade schema.

    仅删除 validity_days 列；回填值属于可重建的派生数据，无需恢复。
    """
    op.drop_column("membership_cards", "validity_days")
