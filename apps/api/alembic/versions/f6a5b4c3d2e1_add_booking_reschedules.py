"""add_booking_reschedules

F6.5 原子改期/改派：新增审计 + 幂等表 booking_reschedules。

设计要点（D-10）：
  - 所有关联 id 为裸 BIGINT 快照，**不建任何外键**：排期硬删除会级联删除
    booking，FK RESTRICT 会阻断删除、CASCADE 会丢审计；
  - 同一旧预约至多一条改期记录：部分唯一索引
    uq_booking_reschedules_old_reschedule（仅 operation_type='reschedule'）；
  - 幂等键在租户内唯一：部分唯一索引
    uq_booking_reschedules_request_key（request_key IS NOT NULL）。

upgrade：建表（含 tenant_id FK）+ 1 个 CheckConstraint + 5 个索引（新表为空，无锁表风险）。
downgrade：删除 5 个索引后删表（审计数据不可恢复，回滚前需导出）。

Revision ID: f6a5b4c3d2e1
Revises: a7b8c9d0e1f2
Create Date: 2026-10-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a5b4c3d2e1"
down_revision: str | Sequence[str] | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "booking_reschedules",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("public_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        # TenantMixin 声明 tenant_id -> tenants.id (CASCADE) 且 index=True，
        # 迁移必须与模型一致，否则 alembic check 会报 schema drift。
        sa.Column(
            "tenant_id",
            sa.BigInteger(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("old_booking_id", sa.BigInteger(), nullable=False),
        sa.Column("new_booking_id", sa.BigInteger(), nullable=False),
        sa.Column("old_schedule_id", sa.BigInteger(), nullable=False),
        sa.Column("new_schedule_id", sa.BigInteger(), nullable=False),
        sa.Column("old_membership_card_id", sa.BigInteger(), nullable=True),
        sa.Column("new_membership_card_id", sa.BigInteger(), nullable=True),
        sa.Column("operation_type", sa.String(length=20), nullable=False),
        sa.Column("request_key", sa.String(length=64), nullable=True),
        sa.Column("operator_id", sa.BigInteger(), nullable=True),
        sa.Column("remark", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "operation_type IN ('reschedule','card_swap')",
            name="ck_booking_reschedules_type",
        ),
    )

    op.create_index(
        "ix_booking_reschedules_tenant_id",
        "booking_reschedules",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "uq_booking_reschedules_old_reschedule",
        "booking_reschedules",
        ["tenant_id", "old_booking_id"],
        unique=True,
        postgresql_where=sa.text("operation_type = 'reschedule'"),
    )
    op.create_index(
        "uq_booking_reschedules_request_key",
        "booking_reschedules",
        ["tenant_id", "request_key"],
        unique=True,
        postgresql_where=sa.text("request_key IS NOT NULL"),
    )
    op.create_index(
        "idx_booking_reschedules_tenant_created",
        "booking_reschedules",
        ["tenant_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "idx_booking_reschedules_new_booking",
        "booking_reschedules",
        ["tenant_id", "new_booking_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema.

    先删索引再删表；表内审计数据随表删除且不可恢复。
    """
    op.drop_index(
        "idx_booking_reschedules_new_booking",
        table_name="booking_reschedules",
    )
    op.drop_index(
        "idx_booking_reschedules_tenant_created",
        table_name="booking_reschedules",
    )
    op.drop_index(
        "uq_booking_reschedules_request_key",
        table_name="booking_reschedules",
    )
    op.drop_index(
        "uq_booking_reschedules_old_reschedule",
        table_name="booking_reschedules",
    )
    op.drop_index(
        "ix_booking_reschedules_tenant_id",
        table_name="booking_reschedules",
    )
    op.drop_table("booking_reschedules")
