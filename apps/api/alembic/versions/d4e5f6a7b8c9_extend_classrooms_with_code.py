"""extend_classrooms_with_code

classrooms 表新增 code / location / cover_image_url 三列，
code 回填规则：R- 前缀 + id 左补零至 3 位（按租户内唯一约束执行），
回填后再 ADD NOT NULL + UNIQUE。

upgrade：ADD COLUMN code / location / cover_image_url → UPDATE 回填 → code NOT NULL → 加 UNIQUE
downgrade：DROP CONSTRAINT uq_classrooms_tenant_code → DROP COLUMN cover_image_url / location / code

Revision ID: d4e5f6a7b8c9
Revises: b8c9d0e1f2a3
Create Date: 2026-10-26

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """新增 classrooms.code / location / cover_image_url，回填 code 后加唯一约束。"""
    # 1) 先以可空状态新增 code（便于回填）
    op.add_column("classrooms", sa.Column("code", sa.String(length=50), nullable=True, comment="教室编码（租户内唯一）"))
    # 2) 新增可空列
    op.add_column("classrooms", sa.Column("location", sa.String(length=200), nullable=True, comment="位置"))
    op.add_column("classrooms", sa.Column("cover_image_url", sa.String(length=500), nullable=True, comment="封面 object_key"))

    # 3) 回填 code：R- 前缀 + id 左补零至 3 位（PostgreSQL 原生语法）
    op.execute("UPDATE classrooms SET code = 'R-' || LPAD(id::text, 3, '0') WHERE code IS NULL")

    # 4) 回填完毕后强制 NOT NULL
    op.alter_column(
        "classrooms",
        "code",
        existing_type=sa.String(length=50),
        nullable=False,
        comment="教室编码（租户内唯一）",
    )

    # 5) 租户内唯一约束（保留既有 uq_classrooms_tenant_name 不删）
    op.create_unique_constraint(
        "uq_classrooms_tenant_code",
        "classrooms",
        ["tenant_id", "code"],
    )


def downgrade() -> None:
    """删除 classrooms 新增的 3 列及唯一约束。"""
    op.drop_constraint("uq_classrooms_tenant_code", "classrooms", type_="unique")
    op.drop_column("classrooms", "cover_image_url")
    op.drop_column("classrooms", "location")
    op.drop_column("classrooms", "code")
