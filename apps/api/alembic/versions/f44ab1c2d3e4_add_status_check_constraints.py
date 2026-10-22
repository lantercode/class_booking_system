"""add_status_check_constraints

为核心表 status 字段新增 Check 约束，在数据库层防止非法状态值：
  - bookings.status          IN (1,2,3,4,5)   （BookingStatus: BOOKED/CANCELLED/CHECKED_IN/COMPLETED/NO_SHOW）
  - course_schedules.status  IN (1,2,3)       （ScheduleStatus: NORMAL/CANCELLED/FINISHED）
  - membership_cards.status  IN (0,1,2,3,6)   （CardStatus: PENDING/ACTIVE/EXPIRED/FROZEN/CANCELLED）

upgrade（同一事务内，原子完成）：
  1. 越界防御性校验：逐表统计 NOT IN 合法集合的行数；若存在越界行，
     抛出 RuntimeError 使整批回滚并提示先人工修正——非法 status 没有
     语义安全的自动修正目标（不同于 F4.1/F4.2 的 FK 孤立可置 NULL），
     静默 UPDATE 会掩盖数据问题，故采用 fail-fast 而非防御性清理。
  2. 三张表分别 ADD CONSTRAINT ... CHECK (status IN (...))。
     dev 库实测越界 0 行（bookings {2,5} / course_schedules {2,3} /
     membership_cards {0,1,2,3,6}），校验通过直接建约束。

downgrade：按 upgrade 反序 drop 三个 Check 约束（不动任何数据）。

Revision ID: f44ab1c2d3e4
Revises: f42cd3e4f5a6
Create Date: 2026-10-02

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f44ab1c2d3e4"
down_revision: str | Sequence[str] | None = "f42cd3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# 约束名显式声明（与三张表 ORM 模型 __table_args__ 的 CheckConstraint 一致，
# 便于 downgrade 精确 drop，避免 PG 自动命名在不同环境不一致）
CK_BOOKINGS_STATUS = "ck_bookings_status"
CK_COURSE_SCHEDULES_STATUS = "ck_course_schedules_status"
CK_MEMBERSHIP_CARDS_STATUS = "ck_membership_cards_status"

# (表名, 约束名, 合法 status 值集合)
# 合法值与 ORM 枚举一一对应：
#   BookingStatus  (booking/models.py)  : 1..5
#   ScheduleStatus (schedule/models.py) : 1..3
#   CardStatus     (membership/models.py): 0,1,2,3,6
SPECS: tuple[tuple[str, str, tuple[int, ...]], ...] = (
    ("bookings", CK_BOOKINGS_STATUS, (1, 2, 3, 4, 5)),
    ("course_schedules", CK_COURSE_SCHEDULES_STATUS, (1, 2, 3)),
    ("membership_cards", CK_MEMBERSHIP_CARDS_STATUS, (0, 1, 2, 3, 6)),
)


def _in_list(values: tuple[int, ...]) -> str:
    return ", ".join(str(v) for v in values)


def upgrade() -> None:
    """Upgrade schema.

    步骤（同一事务内，原子完成）：
      1. 越界防御性校验（fail-fast）：任一表存在越界 status 行即抛错回滚，
         提示人工修正后重跑；不做静默 UPDATE（无语义安全的修正目标）。
      2. 三张表分别 ADD CONSTRAINT CHECK (status IN (...))。
    """
    conn = op.get_bind()

    # 1. 越界校验（T4.4.1/T4.4.2/T4.4.3 前置）
    violations: list[str] = []
    for table, _name, values in SPECS:
        allowed = _in_list(values)
        rows = conn.execute(
            sa.text(
                f"SELECT status, COUNT(*) AS c FROM {table} "  # noqa: S608
                f"WHERE status NOT IN ({allowed}) GROUP BY status ORDER BY status"
            )
        ).all()
        if rows:
            detail = ", ".join(f"status={r[0]} x{r[1]}" for r in rows)
            violations.append(f"{table}: {detail}")
    if violations:
        raise RuntimeError(
            "F4.4 status Check 约束升级中止：发现越界 status 行（"
            + "; ".join(violations)
            + "）。非法状态值无语义安全的自动修正目标，请先人工核查修正后重跑 migration。"
        )

    # 2. 加 Check 约束（T4.4.1/T4.4.2/T4.4.3）
    for table, name, values in SPECS:
        op.create_check_constraint(
            constraint_name=name,
            table_name=table,
            condition=f"status IN ({_in_list(values)})",
        )


def downgrade() -> None:
    """Downgrade schema.

    仅按 upgrade 反序 drop 三个 Check 约束；不动任何数据
    （约束本身不改变存量数据，无需恢复）。
    """
    for table, name, _values in reversed(SPECS):
        op.drop_constraint(
            constraint_name=name,
            table_name=table,
            type_="check",
        )
