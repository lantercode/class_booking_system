# F4.1 — 恢复 bookings.membership_card_id 外键 · 用户流程

> 视角：本 Feature 为纯数据库结构变更，无 HTTP 用户交互流程。以下描述"DB 层外键约束 + migration 清理"在各场景下的行为，供验收与回归参考。
> 业务身份链路（`current_user` / `tenant_id`）不在本 Feature 范围；FK 在 DB 层对所有写入路径一视同仁。

---

## 流程 1：正常创建 booking 引用存在的会员卡（DB 层放行）

1. 业务层（Service）创建 `Booking(membership_card_id=<存在的卡 id>, ...)`。
2. `INSERT INTO bookings ...` 经 FK 校验：`membership_card_id` 在 `membership_cards.id` 中存在 → 放行。
3. `db.commit()` → booking 落库，`membership_card_id` 保持指向该卡。

**异常**：业务层传入的 `membership_card_id` 为 NULL（无卡预约）→ FK 不校验 NULL（`ON DELETE SET NULL` 列允许 NULL）→ 放行。

## 流程 2：创建 booking 引用不存在的会员卡（DB 层拒绝，AC-3）

1. 业务层（或脏数据）尝试 `INSERT INTO bookings ... membership_card_id=999999999`（不存在）。
2. FK 校验：`999999999 NOT IN membership_cards.id` → `IntegrityError`（`foreign key constraint "fk_bookings_membership_card_id" violates`）。
3. 事务回滚，booking 未落库。
4. 业务层 Service 捕获或向上传播异常；不会出现"指向不存在卡"的脏数据。

## 流程 3：删除会员卡 → 关联 booking 置 NULL（ON DELETE SET NULL，AC-4）

1. card=100 被 2 个 booking（id=1, id=2）引用（`membership_card_id=100`）。
2. `DELETE FROM membership_cards WHERE id=100`。
3. FK 触发 `ON DELETE SET NULL`：`UPDATE bookings SET membership_card_id=NULL WHERE membership_card_id=100`。
4. 结果：booking id=1/id=2 仍存在，`membership_card_id=NULL`。
5. 后续业务层取消这些 booking 时 `if booking.membership_card_id:` 短路 → 不调用 `restore_credit`（无卡可回补），与"无卡预约"行为一致。

## 流程 4：migration 清理孤立数据（AC-5 / AC-6）

**upgrade 前（4 条孤立）**
```
bookings: 11 行，其中 10 行 membership_card_id 非空
孤立: 4 行（membership_card_id 指向不存在的 membership_cards.id）
```

**upgrade 执行（同一事务）**
1. `UPDATE bookings SET membership_card_id = NULL WHERE membership_card_id IS NOT NULL AND membership_card_id NOT IN (SELECT id FROM membership_cards)` → 4 行被置 NULL。
2. `ALTER TABLE bookings ADD CONSTRAINT fk_bookings_membership_card_id FOREIGN KEY (membership_card_id) REFERENCES membership_cards(id) ON DELETE SET NULL` → 此时无孤立，加约束成功。
3. `COMMIT` → alembic_version = `f41ab2c3d4e5`。

**upgrade 后**
```
bookings: 11 行，其中 6 行 membership_card_id 非空（均指向存在的卡）
孤立: 0 行
FK: fk_bookings_membership_card_id ON DELETE SET NULL 已建立
```

**downgrade（回滚）**
1. `ALTER TABLE bookings DROP CONSTRAINT fk_bookings_membership_card_id` → FK 移除。
2. 不恢复孤立数据（原始指向的卡本就不存在，无可恢复信息）。
3. `COMMIT` → alembic_version = `211f847af16c`。

## 流程 5：跨层调用链（不变）

```
Service（不变）→ Repository（不变）→ SQLAlchemy → PostgreSQL（新增 FK 约束）
```

- Service / Repository 代码零改动：FK 约束在 DB 层，对 ORM `INSERT`/`DELETE` 透明。
- `MembershipCardService.restore_credit` / `BookingService._do_cancel_booking` 等既有逻辑不变；它们在 `membership_card_id IS NULL` 时已正确短路。
- 租户隔离：FK 约束是跨租户的引用完整性（`membership_cards.id` 全局唯一主键），不影响 `TenantAwareRepository` 的 `tenant_id` 过滤语义。

## 流程 6：回归场景（FK 不破坏既有行为）

- 取消排期回补课时（F2.4）：`cancel_schedule` 内 `if booking.membership_card_id:` → 非 NULL 才调 `restore_credit`；置 NULL 的 booking 跳过回补，与既有"无卡预约"一致。
- 签到/完成行锁（F2.3）：不涉及 `membership_card_id`，不受影响。
- 预约归属（F2.2）：按 `student_id`/`schedule_id` 过滤，不受 `membership_card_id` FK 影响。
