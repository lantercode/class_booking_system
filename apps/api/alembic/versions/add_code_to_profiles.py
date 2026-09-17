"""add code to profiles

Revision ID: add_code_to_profiles
Revises: add_user_code_to_users
Create Date: 2026-09-17 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone
import random


revision = 'add_code_to_profiles'
down_revision = 'add_user_code_to_users'
branch_labels = None
depends_on = None


def generate_code(prefix: str) -> str:
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_digits = "".join([str(random.randint(0, 9)) for _ in range(6)])
    return f"{prefix}{date_str}{random_digits}"


def upgrade() -> None:
    op.add_column('teacher_profiles', sa.Column('teacher_code', sa.String(20), nullable=True, comment='教师编号'))
    op.create_index('idx_teacher_profiles_code', 'teacher_profiles', ['teacher_code'], unique=True)
    
    op.add_column('student_profiles', sa.Column('student_code', sa.String(20), nullable=True, comment='学员编号'))
    op.create_index('idx_student_profiles_code', 'student_profiles', ['student_code'], unique=True)
    
    conn = op.get_bind()
    teacher_rows = conn.execute(sa.text("SELECT id FROM teacher_profiles")).fetchall()
    for row in teacher_rows:
        conn.execute(sa.text("UPDATE teacher_profiles SET teacher_code = :code WHERE id = :id"), {"id": row[0], "code": generate_code("T")})
    
    student_rows = conn.execute(sa.text("SELECT id FROM student_profiles")).fetchall()
    for row in student_rows:
        conn.execute(sa.text("UPDATE student_profiles SET student_code = :code WHERE id = :id"), {"id": row[0], "code": generate_code("S")})


def downgrade() -> None:
    op.drop_index('idx_student_profiles_code', table_name='student_profiles')
    op.drop_column('student_profiles', 'student_code')
    op.drop_index('idx_teacher_profiles_code', table_name='teacher_profiles')
    op.drop_column('teacher_profiles', 'teacher_code')