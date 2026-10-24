# F6.0 会员卡业务能力盘点（Feature Inventory）

> 日期：2026-10-09
> 性质：**只读审计 + 原型规划**，未修改任何业务代码与数据库
> 方法：以真实代码为唯一依据，每项结论附 file:line 证据；不确定项标 `待确认`
> 关联：docs/delivery/execution-board.md、docs/delivery/feature-backlog.md（Epic 1-5 全部 DONE，本盘点基于其完成后的代码现状）

## 状态图例

- ✅ 已实现：端到端可用，有代码与测试证据
- 🟡 部分实现：核心链路存在但有明确缺口
- ❌ 未实现：代码中不存在
- ❓ 待确认：实现存在但语义/边界未定义

---

## 1. 会员卡类型、套餐、购买与发放

| 子项 | 状态 | 证据 |
|------|------|------|
| 卡产品（套餐）独立模型 | ✅ | `apps/api/src/app/modules/membership/models.py:83-145` `MembershipCardProduct`：name/card_type/price/total_credits/validity_days/applicable_course_ids/max_weekly_usage/status/软删除 |
| 卡类型三分类 | ✅ | `membership/models.py:41-45` `CardType`：count（次卡）/period（期限卡）/unlimited（不限次） |
| 产品 CRUD + 回收站 | ✅ | `membership/router.py` products 端点组（create/update/delete/batch-delete/recycle-bin/restore），admin 装饰器齐全 |
| 管理端发卡 | ✅ | `membership/service.py:228-470` `issue_card`：按产品发卡、重复卡/冲突检查、`allow_duplicate` 续卡、生成卡号、ISSUE 流水 |
| 学员在线购卡（下单→支付→发卡） | ❌ | 无购卡端点；`order/`、`payment/` 模块仅存空壳模型（F6.1 支付渠道属 Future Phase） |
| 实物/线下售卡补录 | 🟡 | admin 发卡可当补录用，但无"购买订单"凭证记录 |

## 2. 学员会员卡列表、详情、余额和有效期

| 子项 | 端 | 状态 | 证据 |
|------|----|----|------|
| 我的卡列表 | 小程序 | ✅ | `apps/miniapp/src/pages/student/membership/index.vue:946` `membershipApi.getMyCards()`；后端 `GET /membership/my-cards` |
| 卡列表 | 管理端 | ✅ | `apps/admin-web/src/views/membership/index.vue:659-681`（含四态） |
| 卡详情页（单卡全量信息） | 小程序 | ❌ | `pages.json` 无卡详情页；API 已备（`miniapp/src/api/index.ts:623` `getCardDetail`）但无页面消费 |
| 使用记录/流水页 | 小程序 | ❌ | API 已备（`getTransactions`，`miniapp/src/api/index.ts:635`）但无页面 |
| 余额与有效期展示 | 小程序 | ✅ | 卡列表展示 remaining/expire_at（booking-confirm 选卡页同样展示：`booking-confirm/index.vue:519-523`） |
| 管理端卡详情+流水 | 管理端 | 🟡 | api-client 有 `getTransactions`（`packages/api-client/src/membership.ts:229-237`）；admin 会员卡页未见流水展示 |

## 3. 卡状态机（未激活/首次核销激活/使用中/用尽/过期/停用）

| 子项 | 状态 | 证据 |
|------|------|------|
| 状态枚举 | ✅ | `membership/models.py:49-57` `CardStatus`：PENDING=0 / ACTIVE=1 / EXPIRED=2 / FROZEN=3 / CANCELLED=6 |
| 未激活（PENDING）→ 激活 | ✅ | 三条激活路径：学员自助 `POST /cards/{id}/activate`、管理员 `admin-activate`、定时任务按生效时间自动激活（`membership/scheduler.py:106-244`） |
| **首次核销激活**（首次签到才激活） | ❌ | `booking/service.py:275-332` check-in/complete 只改预约状态，不触碰卡；激活与核销无耦合。**任务假设与现状不符，见 open-decisions D1** |
| 使用中（ACTIVE） | ✅ | 即 ACTIVE 态 |
| **用尽**（次卡 remaining=0） | ❌ 无独立状态 | 枚举无 EXHAUSTED；扣完仍是 ACTIVE、remaining=0。前端靠 remaining 判断（`booking-confirm/index.vue:519-523`）。**见 D2** |
| 过期 | ✅ | `membership/scheduler.py:51-103`：expire_at < now 且 ACTIVE → EXPIRED，次卡剩余清零 + EXPIRE 流水 |
| 停用/作废 | ✅ | `membership/service.py:800-930` cancel_card / batch_cancel_cards + CANCELLED 流水 |
| 冻结/解冻 | ✅ | freeze/unfreeze/admin-unfreeze（含同课程类型冲突检查 `conflict-check`），F4.3 已做锁排序 |
| 状态 Check 约束 | ✅ | F4.4 DONE；DB 层 `ck_bookings_status` 等约束已在（`booking/models.py:66-70`） |

## 4. 多张卡的计划分配、顺延、替代与时间重叠

| 子项 | 状态 | 证据 |
|------|------|------|
| 预约时绑定具体卡 | ✅ | `bookings.membership_card_id`（FK，ON DELETE SET NULL，F4.1）`booking/models.py:51-54` |
| 多卡场景选卡 | ✅ | 小程序 booking-confirm：拉 my-cards → 过滤可用卡 → 默认推荐 → 手动切换（`booking-confirm/index.vue:642-672`） |
| 卡与排期时间重叠/冻结冲突检查 | ✅ | `GET /cards/{id}/conflict-check`（解冻场景）；admin 端 `checkConflict()`+`unfreezeWithConflict()`（`admin-web membership/index.vue:928-984`） |
| **计划卡失效后的自动顺延/替代** | ❌ | 无任何实现：卡过期/作废/冻结后，既有 BOOKED 预约不重校验，签到时也不检查卡状态。**见 D3** |
| 预约后更换计划卡（改派） | ❌ | 无端点 |
| 改期（reschedule） | ❌ | 只有取消+重约；无原子改期端点 |

## 5. 课程预约、取消、改期及课时预留

| 子项 | 状态 | 证据 |
|------|------|------|
| 创建预约并**即时扣次**（预扣模式） | ✅ | `booking/service.py:130-155`：create 时调 `membership_card_service.deduct_credit`，同一事务（auto_commit=False），扣次失败整体回滚 |
| 取消预约并回补 | ✅ | `booking/service.py:199-269` `_do_cancel_booking`：FOR UPDATE 行锁 → 状态校验 → `restore_credit`（RESTORE 流水） |
| 同排期防重复有效预约 | ✅ | 部分唯一索引 `uq_bookings_schedule_student_active` (schedule_id, student_id) WHERE status IN (1,3,4)（`booking/models.py:71-77`） |
| 预约归属与越权修复 | ✅ | F2.2 DONE |
| 签到/完成行锁 | ✅ | F2.3 DONE（`get_by_id_for_update`） |
| 排期创建并发安全 | ✅ | F4.5 DONE（SERIALIZABLE 快照谓词读） |
| 原子改期 | ❌ | 无端点，改期=取消+重约（存在两次扣/回补的中间态） |
| 预约时对卡状态的前置校验范围 | ❓ | deduct_credit 校验余额与状态，但 PENDING 卡、冻结卡、过期当天卡能否预约的具体边界**待确认**（D4） |

## 6. 教师/管理员签到、考勤和课时核销

| 子项 | 端 | 状态 | 证据 |
|------|----|----|------|
| 排期学员名单 | 教师端 Web | ✅ | `apps/teacher-web/src/views/students/index.vue:139` `bookingApi.list({schedule_id})`（真实 API，非 mock） |
| 签到（check-in） | 教师端 Web | ✅ | `students/index.vue:171` `bookingApi.checkIn()`；后端 `POST /bookings/{id}/check-in`（`require_permissions("booking:manage")`） |
| 完成（complete） | 教师端 | 🟡 | 后端端点存在（`booking/router.py`）；teacher-web 名单页未见 complete 按钮调用 |
| 签到时再次核销/扣次 | ❌（设计如此） | 现状为**预约时预扣**，签到仅确认出勤，不产生二次核销。原型需明确表达该模型，避免"签到扣次"误解 |
| 管理端代预约/代签到 | 🟡 | BookingSource 枚举有 ADMIN/TEACHER（`booking/models.py:19-22`）；管理端无预约管理页 |
| 小程序教师端签到 | ❌ | miniapp `pages/teacher/` 只有 courses/schedule/students/profile，无签到动作页（teacher-web 名义上是 Web） |

## 7. 核销记录、撤销、退款及审计

| 子项 | 状态 | 证据 |
|------|------|------|
| 卡流水（兼任核销记录） | ✅ | `membership/models.py:257-300` `MembershipCardTransaction`：type（ISSUE/CONSUME/RESTORE/RECHARGE/REFUND/ADJUST/EXPIRE）、booking_id、idempotency_key、operator_id、remark |
| 幂等键 | ✅ | 流水表有 idempotency_key；F4.4/F4.5 保障并发一致 |
| 流水查询端点 | ✅ | `GET /membership/transactions`（api-client `getTransactions`、miniapp 均已接） |
| 管理端/学员端流水 UI | ❌ | 两端均无流水页面 |
| 撤销核销（逆向 CONSUME 调整） | 🟡 | 有 ADJUST/RESTORE 机制可承载，但无"撤销某笔核销"的产品化端点 |
| 退款 | ❌ | REFUND 枚举存在（`membership/models.py:59-69`），service/router 无退款实现；支付未接（F6.1） |
| 审计日志（谁在何时改了卡状态） | 🟡 | 流水的 operator_id 只覆盖次数变动；状态变更（冻结/解冻/作废）无独立审计表，仅字段留痕（frozen_reason/cancelled_reason） |

## 8. 管理后台会员卡管理与学员端查询

| 子项 | 端 | 状态 | 证据 |
|------|----|----|------|
| 卡产品管理页 | 管理端 | ✅ | `apps/admin-web/src/views/card-types/index.vue:364-459`（创建/更新/上下架/删除/批量删除） |
| 会员卡管理页 | 管理端 | ✅ | `views/membership/index.vue`：发放/激活/冻结/解冻（含冲突处理）/作废/批量作废，四态齐全 |
| 管理端延期（extend） | 🟡 | 后端 `POST /cards/{id}/extend` 存在；admin 页面未暴露入口 |
| 管理端预约管理页 | ❌ | admin-web 路由（`router/index.ts:22-89`）无 bookings 页面——**管理端看不到预约** |
| 学员端 Web 查询 | ❌ | `apps/student-web` 全目录 grep `membership` 零命中——学员 Web 端无任何会员卡能力 |
| 小程序会员卡中心 | ✅ | `pages/student/membership/index.vue`（列表+激活+学生解冻+空态引导） |

## 9. 角色权限、租户隔离、异常处理与跨端状态同步

| 子项 | 状态 | 证据 |
|------|------|------|
| RBAC 装饰器 | ✅（存量债务除外） | membership/booking 端点 `@require_roles` / `@require_permissions` 覆盖见端点表；F1.1 已 DONE（bypass=False） |
| 租户隔离 | ✅ | 三层隔离 + TenantAwareRepository（F1.5 scheduler 租户循环已修）；外键/Check 约束 F4.1/F4.2/F4.4 已落 |
| 401 统一刷新 | ✅ | packages/api-client 与 miniapp 双层各自实现（v3 协议 R7 双侧一致） |
| 列表四态 | ✅ | F3.4 DONE（admin membership 页实测有 loading/error/empty） |
| 跨端状态同步 | 🟡 | 无推送机制（F6.2 未做）；学员端签到/扣次结果靠下拉刷新获取 |
| 教师端 API 层归属 | ✅ | teacher-web 实测使用 `@dance-saas/api-client`（`teacher-web/src/views/students/index.vue:95`） |

---

## 汇总

| # | 能力域 | 结论 |
|---|--------|------|
| 1 | 卡类型/套餐/购买/发放 | 🟡 发放完整，购买未实现 |
| 2 | 学员卡列表/详情/余额/有效期 | 🟡 小程序列表完整，详情与流水页缺 |
| 3 | 卡状态机 | 🟡 5 态闭环，缺"用尽"态与首次核销激活（设计差异见 D1/D2） |
| 4 | 多卡分配/顺延/替代/重叠 | 🟡 选卡+冲突检查有，顺延/替代/改派无 |
| 5 | 预约/取消/改期/预留 | 🟡 预扣-回补闭环，原子改期无，预扣模式语义待确认 |
| 6 | 签到/考勤/核销 | 🟡 教师端可签到；核销=预约预扣，无签到二次核销 |
| 7 | 核销记录/撤销/退款/审计 | 🟡 流水完备，撤销/退款/审计 UI 缺 |
| 8 | 后台管理与学员查询 | 🟡 管理端缺预约页与延期入口；学员 Web 端空白 |
| 9 | 权限/租户/异常/同步 | ✅ 基线完整（跨端推送除外） |
