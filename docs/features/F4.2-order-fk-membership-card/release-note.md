# F4.2 — Release Note

## 恢复 orders.membership_card_id 外键 + 索引（2026-09-29）

### 功能变更

- 恢复 `orders.membership_card_id -> membership_cards.id` 外键约束 `fk_orders_membership_card_id`（`ON DELETE SET NULL`）。该列由 `57aeb9dcf020` migration 新增时仅落库 `BigInteger` 未带外键；Order ORM 模型亦无 ForeignKey；本 Feature 补回 FK 并新增索引。
- Alembic migration `f42cd3e4f5a6`（`down_revision=f41ab2c3d4e5`，接 F4.1）在同一事务内：
  1. 防御性清理孤立 order（`membership_card_id` 指向不存在的卡）置 NULL（dev 库当前 0 条，生产可能非 0）；
  2. 重建外键 `fk_orders_membership_card_id`（`ON DELETE SET NULL`）；
  3. 新增索引 `ix_orders_membership_card_id`（加速 `ON DELETE SET NULL` 行定位 + 按卡反查订单）。
- ORM 模型 `Order.membership_card_id` 补回 `ForeignKey("membership_cards.id", ondelete="SET NULL")`，并在 `__table_args__` 新增 `Index("ix_orders_membership_card_id", "membership_card_id")`，使模型与 DB 一致。

### 兼容性

- API 路径、方法、请求体、响应模型全部不变；无端点变更 → 无需 `pnpm gen:types`。
- 模型列 `membership_card_id` 类型仍为 `BigInteger`（nullable=True），仅新增 FK 元数据 → DTO 字段集合不变。
- 前端 4 端影响评估：
  - admin-web / teacher-web / student-web / miniapp：不直接感知 DB FK / 索引；订单/支付端点契约不变（order 模块当前无 router） → **均不涉及**。
- Service / Repository / Router / schemas **零改动**：FK + 索引在 DB 层，对 ORM 透明；`payment/service.py` L61 `if order.membership_card_id:` 短路模式在置 NULL 后仍正确工作。

### 修复

- 恢复 DB 层引用完整性 + 加索引支撑：
  - 修复前：`membership_card_id` 无 FK 无索引，DB 无法阻止插入指向不存在会员卡的订单（dev 库当前 0 条孤立，生产可能存在）。
  - 修复后：FK 在 DB 层强制 `membership_card_id` 必须指向存在的卡（或 NULL）；删卡时关联 order 自动置 NULL（订单本身保留）；索引 `ix_orders_membership_card_id` 加速 FK 触发器行定位与未来按卡反查订单。

### 运维与数据

- **数据库结构变更**：新增 FK `fk_orders_membership_card_id`（`ON DELETE SET NULL`）+ 新增索引 `ix_orders_membership_card_id`（`btree (membership_card_id)`）。
- **数据变更**：dev 库 0 条孤立被防御性清理（受影响 0 行）；生产若有孤立也将被置 NULL（语义为"无关联卡"）。
- migration 可逆：`downgrade` drop index + drop FK（不恢复孤立数据，原始指向的卡本不存在）；`upgrade` 重新清理 + 建 FK + 建索引。
- 无配置 / 环境变量变更。
- 无 Redis key 结构变更。

### 部署步骤

```bash
# 1. 应用 migration（清理孤立 + 建 FK + 建索引，同一事务原子完成）
cd apps/api && PYTHONPATH=src .venv/bin/alembic upgrade head
# → Running upgrade f41ab2c3d4e5 -> f42cd3e4f5a6

# 2. 验证
cd apps/api && PYTHONPATH=src .venv/bin/python -c "
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import get_settings
async def main():
    s = get_settings(); eng = create_async_engine(s.DATABASE_URL, pool_pre_ping=True)
    async with eng.connect() as c:
        fk = (await c.execute(text(\"SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='orders'::regclass AND conname='fk_orders_membership_card_id'\"))).scalar()
        ix = (await c.execute(text(\"SELECT indexdef FROM pg_indexes WHERE tablename='orders' AND indexname='ix_orders_membership_card_id'\"))).scalar()
        orphan = (await c.execute(text(\"SELECT COUNT(*) FROM orders o LEFT JOIN membership_cards m ON o.membership_card_id=m.id WHERE o.membership_card_id IS NOT NULL AND m.id IS NULL\")).scalar()
        print('FK:', fk); print('Index:', ix); print('orphan:', orphan)
    await eng.dispose()
asyncio.run(main())
"
# 期望：FK 含 ON DELETE SET NULL；Index 含 btree (membership_card_id)；orphan=0

# 3. 回滚（如需）
cd apps/api && PYTHONPATH=src .venv/bin/alembic downgrade -1
# → Running downgrade f42cd3e4f5a6 -> f41ab2c3d4e5
```

### 已知遗留（后续处理）

- 生产灰度并发风险：upgrade 前 DB 无 FK，并发写入仍可产生新孤立；建议生产在维护窗口或先停写再 upgrade。
- `bookings.membership_card_id` 仍无索引（F4.1 D7 评估量级小未加；本 Feature 不扩大到 bookings；如未来 bookings 量级增长可另立 Feature 加索引）。
- order 模块当前仅有 models.py（无 service/router/repository），未来实现支付/购卡流程时创建 Order 的路径需经全局异常处理器捕获 `IntegrityError` 返回统一信封。
