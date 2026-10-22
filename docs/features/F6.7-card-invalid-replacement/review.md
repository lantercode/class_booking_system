# F6.7 最终 Review：卡失效替代与受影响预约（D3）

> 日期：2026-10-22。Reviewer：project-architect（Stage 10 门禁复核，非重新设计）。
> 复核方式：7 份产物 + 全部 10 个白名单改动文件逐一读码核对 + git diff 范围验证；未修改任何业务代码。

## 1. Findings

### Blocker（0 项）

无。

### Major（0 项）

无。

### Minor（3 项，均登记为技术债，不阻断验收）

| # | 发现 | 证据 | 影响与建议 |
|---|------|------|-----------|
| M-1 | api-client barrel 未导出 `AffectedBookingItem` / `AffectedBookingsResponse`，admin-web 以 `ReturnType` 推导替代 | [index.ts:L172-185](file:///Users/lixiang/Desktop/class_booking_system/packages/api-client/src/index.ts#L172-L185)（导出清单无新类型）；[index.vue:L650-651](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/membership/index.vue#L650-L651) | 类型仍单一事实源（定义在 membership.ts 内），无运行时影响；下次触碰 barrel 时补导出。登记 **D-F6.7-1** |
| M-2 | acceptance C-9 写「page_size=0/101 → 400」，实际为 422 | [error_handler.py 不覆盖 RequestValidationError 的既有约定]；测试文件头注释 [test_membership_affected_bookings.py:L7-11](file:///Users/lixiang/Desktop/class_booking_system/apps/api/tests/test_membership_affected_bookings.py#L7-L11)，断言 422（L801-804）；OpenAPI 亦仅声明 422（openapi.json:L6682-6691） | 项目全局约定一致（非本端点特例），改全局 handler 超白名单；建议修订 acceptance 文档措辞为 422。登记 **D-F6.7-2** |
| M-3 | miniapp 前端 join 为近似口径：`display_status ∈ {1,3}` 对「CHECKED_IN/BOOKED 但已开始」边例为超集 | [index.vue:L397-411](file:///Users/lixiang/Desktop/class_booking_system/apps/miniapp/src/pages/student/bookings/index.vue#L397-L411)；后端 display_status 计算 [service.py:L1397-1415](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L1397-L1415) | 经核对 display_status 语义：`1` ⇔ BOOKED 且 start_at>now（与 K1 精确一致，换卡按钮仅挂此分支，L96-100）；超集边例只多渲染「请联系机构处理」警示（L101），**不暴露换卡入口**，属安全侧过包含；后端 K1 仍为权威口径。登记 **D-F6.7-3** |

### 观察项（非缺陷，不留债）

- `check_roles` 内含全局 `PERMISSION_CHECK_BYPASS` 分支（[checker.py:L360-361](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/core/rbac/checker.py#L360-L361)）：属 project_rules 已登记的既有债务，对本系统所有 RBAC 检查均一生效；F6.7 未新增开关，且在角色判定之外保留独立的归属 403（[service.py:L1264-1265](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L1264-L1265)），满足 E-5「不扩散、不依赖」。
- `booking_service` 单例定义于 booking/router.py:14（既有惯例），membership/router.py 经 `from app.modules.booking.router import booking_service` 复用（[router.py:L18](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/router.py#L18)）；方向为 membership.router → booking.router → booking.service → membership.service，membership.service 不反向 import booking，**无循环 import**，implementation-plan §1.1 的决策成立。
- miniapp 幂等键「每开弹层生成一次、层内重试复用」（[index.vue:L262-263](file:///Users/lixiang/Desktop/class_booking_system/apps/miniapp/src/pages/student/bookings/index.vue#L262-L263)、L420-422）与后端重放语义匹配：同参重放命中 [service.py:L641-658](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L641-L658) 返回原结果；失败请求不落记录，换卡重选可安全复用同键；极端场景（成功响应丢失后换选他卡）会得 409 且不产生任何写操作——失败安全。

## 2. 复核要点逐项结论

### 2.1 分层（PASS）

- 查询落在 `BookingService.get_affected_bookings_by_card`（[service.py:L1233-1303](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L1233-L1303)）；循环 import 规避决策成立（见观察项）。
- 路由零业务判断：[router.py:L292-319](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/router.py#L292-L319) 仅参数提取 + DI + 调 Service；无 `db.commit`（只读）。
- Repository 显式 `tenant_id` + `status IN (BOOKED, CHECKED_IN)` + `start_at > now` + `ORDER BY start_at ASC, id ASC`，返回 `(total, items)`，无业务决策（[repository.py:L421-469](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/repository.py#L421-L469)）。
- 无跨模块 Repository 直调：booking ↔ membership 之间仅经 `membership_card_service.get_card`。

### 2.2 安全 / 租户 / 权限（否决项，PASS）

- 混合角色端点无 `@require_roles`，Service 内 `check_roles(["admin","super_admin"])` + 归属校验完备：admin 任意卡放行（B-9/C-1）、student 本人放行（B-7/C-2）、同租户非本人 403（B-8/C-3）、teacher 视同非本人 403（E-3 实测）。
- 跨租户 404 双保险成立：① `get_card` 经 TenantAwareRepository 自动注入返回 None → 404（[membership/service.py:L493-501](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L493-L501)）；② 预约查询显式 `Booking.tenant_id == tenant_id`——即使卡查询失效，预约数据也不会跨租户泄露。C-4 实测 404 且响应不含卡 ID。
- 身份只取自 JWT（`current_user.get("tenant_id"/"user_id")`，router.py:L313-314），端点不接收身份参数（R-4）。
- 响应无学员 PII（C-2 断言无 student_phone/student_nickname）；403/404 响应无 traceback/SQL/内部信息（C-3/C-4/C-6 断言）。

### 2.3 事务（PASS）

- 新链路纯只读：无 commit/flush/FOR UPDATE；C-10 实测 freeze 后查询结果不变且 `card_status=3`（R-8）。
- git diff 证实事务路径零改动：`membership/service.py` 无 diff；`booking/service.py` 仅 +75 行纯新增（import + 新方法）。
- C-11/C-12 并发断言可信：预约经真实 API 创建（卡 C 有真实 CONSUME 流水），断言覆盖无 500/死锁、状态码 ∈ {200,400,409}、RESTORE/CONSUME 各 ≤1、成功=一补一扣且 affected(C)=0、失败=零流水且预约不悬空、`used_credits` 与流水一致（[test:L894-921](file:///Users/lixiang/Desktop/class_booking_system/apps/api/tests/test_membership_affected_bookings.py#L894-L921)）。账务守恒断言完备。R-5（F6.5 遗留回补路径）顺带关闭。

### 2.4 契约（PASS）

- OpenAPI 与实现一致：`/api/v1/membership/cards/{card_id}/affected-bookings` 唯一路径、无尾斜杠变体（openapi.json:L6606，grep 全库仅 1 命中）；`card_id ge=1`、`page ge=1 默认 1`、`page_size 1..100 默认 20` 与 requirement §4.1 一致。
- 响应字段与 requirement §4.2 逐字段一致（schemas.py:L90-111）；排序 R-10 落实于 repository.py:L462，B-11 乱序创建实测次序稳定。
- 400 vs 422 差异处置可接受：全局既有约定，已登记 M-2/D-F6.7-2。
- 生成物仅 `pnpm gen:types` 产物（openapi.json/schema.d.ts 均 +additive diff）。

### 2.5 前端（PASS）

- **admin-web**：冻结/作废双弹窗四态齐备（loading 骨架 L390/L442、error+重试不阻断 L391-394/L443-446、empty 中性提示 L403/L455、success 警示条+明细 L396-415/L448-467）；确定按钮无 disabled 绑定（L420、L472-478），R-7 不阻断成立；作废弹窗 total>0 时 danger「确定作废」（L477）；请求序号防竞态（L736-761）；≤5 条预览 +「以操作时实际为准」（L750、L413-415/L465-467）。
- **miniapp**：警示条 join 条件 `getCardInvalidText && isAffectedStatus`（L87-89）；BOOKED 渲染换卡、其余渲染「请联系机构处理」（L96-101，R-6）；换卡弹层消费 recommend-card、默认选中 `recommended_card_id`（L442-449）；改派携带幂等键（L469-476，K3）；失败停留弹层可重选（L484-485，D-8）；空态懒加载 `tenant/info.contact_phone` + makePhoneCall、无号降级文案（L154-166、L492-509，U-1 闭环）；my-cards 失败静默降级（L390-394，四态表）。
- 无第三套请求层：admin 经 `membershipCardApi`（packages/api-client），miniapp 经既有 `request()`（api/index.ts）。
- 全部前端调用端点（affected-bookings / reschedule / recommend-card / my-cards / tenant-info）逐一核对后端真实存在。

## 3. AC Traceability

| 组 | 结论 | 证据 |
|----|------|------|
| A-1..A-10 | PASS | static-verification.md 全 PASS；本复核抽验 A-3（router L292-319）、A-4（openapi.json:L6606）、A-6（diff 纯新增）、A-8/A-9（§2.1/§2.3）一致 |
| B-1..B-12 | PASS（11 例） | 测试 L141-503 逐条映射；B-12 的 `page_size>100 拒绝`由 C-9 HTTP 层覆盖（Pydantic Query le=100） |
| C-1..C-10 | PASS | 测试 L512-856；C-9 按 422 断言（M-2 已登记） |
| C-11 / C-12 | PASS | 测试 L864-1025，账务守恒断言见 §2.3 |
| D-1..D-4 | PASS（码审） | §2.5 admin 四态 + 不阻断；运行时交互转 Stage 11 |
| D-5..D-10 | PASS（码审） | §2.5 miniapp；D-6 CHECKED_IN 无换卡按钮（L101）；D-10 无失效卡不渲染（L88 短路） |
| D-11 | PASS | 无第三请求层；gen:types 产物一致 |
| E-1..E-4 | PASS | C-1（admin 200）、C-2/C-3（student 200/403）、C-4（跨租户 404）、C-5（401）、E-3（teacher 403） |
| E-5 | PASS | 无新 bypass 开关；归属 403 独立于角色判定（见观察项 1） |
| F-1..F-6 | 转 Stage 11 | 人工验收项（弹窗实操、真机换卡、权限拒绝、回归），产物已就绪 |

## 4. Boundary Check

| 边界 | 结论 |
|------|------|
| 实际改动 ⊆ 白名单 | PASS（git diff/stat 核对 9 个跟踪文件 + 1 个新增测试文件；生成物纯新增） |
| 冻结/作废/改派/创建预约事务零改动 | PASS（membership/service.py 无 diff；booking/service.py 纯新增） |
| student-web / teacher-web 零改动 | PASS |
| 无 DB 迁移 / 无索引变更 | PASS |
| 历史未提交改动未覆盖 | PASS（工作区大量历史改动与本 Feature 文件无交集冲突） |
| 无循环 import / 无跨模块 Repository | PASS |

## 5. Risk & Tech Debt

- 残留风险：影响面 TOCTOU（R-1）为设计内已知限制，文案「以操作时实际为准」+ C-11/C-12 已验证结果可解释；前端真机交互未运行时验证（转 Stage 11）。
- 新增技术债登记：**D-F6.7-1**（barrel 补导出 `AffectedBookingItem`/`AffectedBookingsResponse`）、**D-F6.7-2**（acceptance C-9 措辞 400→422，与全局约定对齐）、**D-F6.7-3**（miniapp join 近似口径文档化；如未来要精确可在 BookingResponse 增加 `is_affected_candidate` 字段或直接调本端点核对）。

## 6. Conclusion

**READY_FOR_ACCEPTANCE**

0 Blocker / 0 Major / 3 Minor（均已登记技术债，不阻断）。冻结契约 K1–K3 全部落实且经真实代码核对；安全/租户/权限否决项通过；事务边界零侵蚀；AC A–E 全 PASS，F 组转 Stage 11 人工验收。

---

## 附：M6 遥测

| 项 | 值 |
|----|----|
| 工具调用数 | 47（含本文件写入） |
| 起止时间 | 1792674939 → 1792675339（约 6.7 分钟，2026-10-22 Asia/Shanghai） |
| 读取文件清单（行数为读取区间） | 见下 |

| 文件 | 读取行数 |
|------|---------|
| .trae/skills/orchestration/feature-delivery-lifecycle/SKILL.md | 144（全文） |
| docs/features/F6.7-card-invalid-replacement/requirement.md | 166（全文） |
| docs/features/F6.7-card-invalid-replacement/user-flow.md | 91（全文） |
| docs/features/F6.7-card-invalid-replacement/acceptance.md | 101（全文） |
| docs/features/F6.7-card-invalid-replacement/implementation-plan.md | 135（全文） |
| docs/features/F6.7-card-invalid-replacement/implementation-report.md | 71（全文） |
| docs/features/F6.7-card-invalid-replacement/static-verification.md | 19（全文） |
| docs/features/F6.7-card-invalid-replacement/runtime-test-report.md | 40（全文） |
| apps/api/src/app/modules/booking/repository.py | 180（L1-60、L360-479） |
| apps/api/src/app/modules/booking/service.py | 345（L1-59、L630-709、L1225-1324、L1393-1427、grep L1336-1380） |
| apps/api/src/app/modules/booking/schemas.py | 111（L1-111） |
| apps/api/src/app/modules/membership/router.py | 140（L1-60、L255-334）+ git diff 全文 |
| apps/api/src/app/modules/membership/service.py | 30（L488-517） |
| apps/api/src/app/core/rbac/checker.py | 60（L320-379） |
| apps/api/tests/test_membership_affected_bookings.py | 1025（全文） |
| packages/api-client/src/membership.ts | 271（全文） |
| packages/api-client/src/index.ts | 24（L165-188）+ grep |
| packages/api-types/openapi.json | 90（L6606-6695）+ grep |
| apps/admin-web/src/views/membership/index.vue | 125（L363-487）+ grep 69 命中 |
| apps/miniapp/src/api/index.ts | 169（L520-688）+ grep |
| apps/miniapp/src/pages/student/bookings/index.vue | 470（L60-189、L230-304、L365-525）+ grep |
| git status / git diff（白名单 10 文件） | 命令输出 |
