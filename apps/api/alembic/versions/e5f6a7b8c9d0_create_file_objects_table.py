"""create_file_objects_table

upload 模块审计表：file_objects，记录每次上传的文件元数据，
支撑 avatar / classroom_cover / banner / video_cover / notice 等业务场景。

create table + unique(tenant_id, object_key) + idx(tenant_id, biz_type)
downgrade：drop_table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-26

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建 file_objects 审计表。"""
    op.create_table(
        "file_objects",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.BigInteger(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("object_key", sa.String(length=500), nullable=False, comment="存储对象 key（如 t/1/avatar/u_1024_1697.jpg）"),
        sa.Column("mime", sa.String(length=50), nullable=False, comment="MIME 类型"),
        sa.Column("size", sa.BigInteger(), nullable=False, comment="文件字节数"),
        sa.Column("biz_type", sa.String(length=30), nullable=False, comment="业务场景：avatar | classroom_cover | banner | video_cover | notice"),
        sa.Column("uploader_id", sa.BigInteger(), nullable=True, comment="上传者用户 ID"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "object_key", name="uq_file_objects_tenant_key"),
    )
    op.create_index(
        "idx_file_objects_tenant_biz",
        "file_objects",
        ["tenant_id", "biz_type"],
    )


def downgrade() -> None:
    """删除 file_objects 表。"""
    op.drop_table("file_objects")
