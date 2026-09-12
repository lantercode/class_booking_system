"""
迁移脚本：添加课程类型功能

功能：
1. 创建 course_types 表
2. 为 courses 表添加 course_type_code 字段
3. 插入默认课程类型数据
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision = 'add_course_types'
down_revision = 'c3d4e5f6g7h8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 创建 course_types 表
    op.create_table(
        'course_types',
        sa.Column('id', sa.BigInteger, primary_key=True),
        sa.Column('public_id', UUID(as_uuid=True), unique=True, nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', sa.BigInteger, nullable=False),
        sa.Column('name', sa.String(50), nullable=False, comment='类型名称'),
        sa.Column('code', sa.String(50), nullable=False, comment='类型代码'),
        sa.Column('description', sa.Text, comment='描述'),
        sa.Column('required_card_types', ARRAY(sa.String(50)), comment='需要的会员卡类型列表'),
        sa.Column('sort_order', sa.Integer, nullable=False, server_default='0', comment='排序'),
        sa.Column('status', sa.SmallInteger, nullable=False, server_default='1', comment='状态'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )

    # 创建索引
    op.create_index('uq_course_types_tenant_code', 'course_types', ['tenant_id', 'code'], unique=True)
    op.create_index('uq_course_types_tenant_name', 'course_types', ['tenant_id', 'name'], unique=True)
    op.create_index('idx_course_types_tenant_status', 'course_types', ['tenant_id', 'status'])

    # 2. 为 courses 表添加 course_type_code 字段
    op.add_column('courses', sa.Column('course_type_code', sa.String(50), comment='课程类型代码'))
    op.create_index('idx_courses_tenant_type', 'courses', ['tenant_id', 'course_type_code'])

    # 3. 为现有课程设置默认值
    op.execute("UPDATE courses SET course_type_code = 'regular' WHERE course_type_code IS NULL")


def downgrade() -> None:
    # 删除索引
    op.drop_index('idx_courses_tenant_type', 'courses')
    op.drop_index('idx_course_types_tenant_status', 'course_types')
    op.drop_index('uq_course_types_tenant_name', 'course_types')
    op.drop_index('uq_course_types_tenant_code', 'course_types')

    # 删除字段
    op.drop_column('courses', 'course_type_code')

    # 删除表
    op.drop_table('course_types')