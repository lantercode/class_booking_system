"""
迁移脚本：为排期表添加取消相关字段

功能：
1. 添加 cancel_reason 字段（取消原因）
2. 添加 cancelled_by 字段（取消操作人）
3. 添加 cancelled_at 字段（取消时间）
"""

from alembic import op
import sqlalchemy as sa

revision = 'add_schedule_cancel_fields'
down_revision = 'add_applicable_course_type_codes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 添加 cancel_reason 字段
    op.add_column(
        'course_schedules',
        sa.Column('cancel_reason', sa.Text, comment='取消原因')
    )

    # 2. 添加 cancelled_by 字段
    op.add_column(
        'course_schedules',
        sa.Column('cancelled_by', sa.BigInteger, comment='取消操作人ID')
    )

    # 3. 添加 cancelled_at 字段
    op.add_column(
        'course_schedules',
        sa.Column('cancelled_at', sa.DateTime(timezone=True), comment='取消时间')
    )


def downgrade() -> None:
    # 删除添加的字段
    op.drop_column('course_schedules', 'cancelled_at')
    op.drop_column('course_schedules', 'cancelled_by')
    op.drop_column('course_schedules', 'cancel_reason')