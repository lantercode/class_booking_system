"""
迁移脚本：为排期表添加预告内容相关字段

功能：
1. 添加 preview_content 字段（预告内容）
2. 添加 preview_updated_at 字段（预告更新时间）
"""

import sqlalchemy as sa

from alembic import op

revision = "add_schedule_preview_content"
down_revision = "add_schedule_cancel_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 添加 preview_content 字段
    op.add_column(
        "course_schedules",
        sa.Column("preview_content", sa.Text, comment="预告内容（教学内容、视频名称等）"),
    )

    # 2. 添加 preview_updated_at 字段
    op.add_column(
        "course_schedules",
        sa.Column("preview_updated_at", sa.DateTime(timezone=True), comment="预告更新时间"),
    )


def downgrade() -> None:
    # 删除添加的字段
    op.drop_column("course_schedules", "preview_updated_at")
    op.drop_column("course_schedules", "preview_content")
