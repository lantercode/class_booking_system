# F4.4 — Release Note

## 核心表 status 字段 Check 约束（2026-10-02）

### 功能变更

- 为 `bookings` / `course_schedules` / `membership_cards` 三表的 `status` 字段新增 Check 约束，在数据库层防止非法状态值写入：
  - `ck_bookings_status`：`CHECK (status IN (1, 2, 3, 4, 5))`（对应 `BookingStatus`：BOOKED/CANCELLED/CHECKED_IN/COMPLETED/NO_SHOW）
  - `ck_course_schedules_status`：`CHECK (status IN (1, 2, 3))`（对应 `ScheduleStatus`：NORMAL/CANCELLED/FINISHED）
  - `ck_membership_cards_status`：`CHECK (status IN (0, 1, 2, 3, 6))`（对应 `CardStatus`：PENDING/ACTIVE/EXPIRED/FROZEN/CANCELLED）
- Alembic migration `f44ab1c2d3e4`（`down_revision=f42cd3e4f5a6`，接 F4.2）在同一事务内：
  1. 越界防御性校验（fail-fast）：逐表统计越界 status 行数；任一表存在越界即抛 `RuntimeError` 回滚并打印明细，提示人工修正后重跑（不静默篡改业务状态）；
  2. 三表分别 `ADD CONSTRAINT ... CHECK (status IN (...))`。
- ORM 模型三张表的 `__table_args__` 补同名 `CheckConstraint`，使模型与 DB 一致。

### 兼容性

- API 路径、方法、请求体、响应模型全部不变；无端点变更 → 无需 `pnpm gen:types`。
- 模型列 `status` 类型仍为 `SmallInteger`（nullable=False），仅新增 CheckConstraint → DTO 字段集合不变。
- 前端 4 端影响评估：admin-web / teacher-web / student-web / miniapp 不直接感知 DB Check 约束；三表对应端点契约不变 → 均不涉及。
- Service / Repository / Router / schemas 零改动：Check 约束在 DB 层，对 ORM 透明；Service 状态机已正确使用枚举，加约束是纵深防御。

### 修复

- 修复 DB 层缺少 status 取值约束的问题：
  - 修复前：任何写入路径（含绕过 Service 的裸 SQL / 修复脚本 / 缺陷代码）均可把 status 写成枚举外的非法值，且难以发现。
  - 修复后：非法 status 在 commit 时被 PostgreSQL Check 约束拦截，抛出 `IntegrityError`，非法行不落库。

### 运维与数据

- **数据库结构变更**：新增 3 个 Check 约束（`ck_bookings_status` / `ck_course_schedules_status` / `ck_membership_cards_status`）。
- **数据变更**：无（Check 约束不修改存量数据）；dev 库实测 0 越界（bookings=11 / course_schedules=33 / membership_cards=17）；生产若有越界 migration 将 fail-fast 回滚并打印明细。
- migration 可逆：`downgrade` 反序 drop 三个 Check 约束（不动数据）；`upgrade` 重新校验 + 建约束。
- 无配置 / 环境变量变更。
- 无 Redis key 结构变更。

### 部署步骤

```bash
# 1. 应用 migration（越界校验 + 建约束，同一事务原子完成）
cd apps/api && PYTHONPATH=src .venv/bin/alembic upgrade head
# → Running upgrade f42cd3e4f5a6 -> f44ab1c2d3e4

# 2. 验证
cd apps/api && PYTHONPATH=src .venv/bin/python -c "
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import get_settings
async def main():
    s = get_settings(); eng = create_async_engine(s.DATABASE_URL, pool_pre_ping=True)
    async with eng.connect() as c:
        for t, n in [('bookings','ck_bookings_status'),('course_schedules','ck_course_schedules_status'),('membership_cards','ck_membership_cards_status')]:
            r = (await c.execute(text(f\"SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='{t}'::regclass AND conname='{n}'\"))).scalar()
            print(n, '->', r)
    await eng.dispose()
asyncio.run(main())
"
# 期望：三约束均存在，定义含正确合法值集合

# 3. 回滚（如需）
cd apps/api && PYTHONPATH=src .venv/bin/alembic downgrade -1
# → Running downgrade f44ab1c2d3e4 -> f42cd3e4f5a6
```

### 已知遗留（后续处理）

- 生产灰度时若存在越界 status 行，upgrade 会 fail-fast 抛错回滚并打印明细（表 / status 值 / 行数），需人工核查修正后重跑。
- `membership_cards` 既有 Check 命名漂移（模型 `chk_credits_range` vs DB `chk_used_credits_valid`/`chk_total_credits_positive`）为存量历史差异，未来 autogenerate 对齐时可另立 Feature。
- 其他带 status 的表（users/courses/classrooms/orders 等）当前未加 Check 约束；如有需求需另立 Feature 评估。
