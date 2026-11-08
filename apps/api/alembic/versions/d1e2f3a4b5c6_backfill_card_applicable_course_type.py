"""backfill_card_applicable_course_type

历史会员卡的 applicable_course_type_code 可能为 NULL（早期语义为“不限课程类型”），
但 2026-11-06 起业务规则改为“所有卡必须指定适用课程类型才可用于预约”，
这些历史卡因此在排期页被判为“无适用卡”。

改动：
  1. 对租户已配置 regular 课程类型的存量卡，将 NULL 回填为 'regular'
     （与 courses 表历史回填口径一致）；
  2. 不修改会员卡产品：产品为空时发卡接口会显式拒绝，要求管理员先配置类型。

Revision ID: d1e2f3a4b5c6
Revises: c1d2e3f4a5b6
Create Date: 2026-11-08

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: str | Sequence[str] | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade data：回填历史卡缺失的适用课程类型。"""
    op.execute(
        """
        UPDATE membership_cards AS c
        SET applicable_course_type_code = 'regular'
        WHERE c.applicable_course_type_code IS NULL
          AND EXISTS (
              SELECT 1 FROM course_types AS ct
              WHERE ct.tenant_id = c.tenant_id
                AND ct.code = 'regular'
          )
        """
    )


def downgrade() -> None:
    """数据回填不可逆：无法区分回填值与原有 NULL，保留现状。"""
    pass
