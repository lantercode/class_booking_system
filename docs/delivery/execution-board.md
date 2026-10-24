# Execution Board

> 生成日期：2026-09-26（最近更新：2026-10-21，见文首更新节）

---

## 更新 2026-10-21：F6.0 决策全部冻结 + 实施路线确定

**产品决策（2026-10-21，用户确认）**：
1. **实施优先级：F6（会员卡业务补全）先于 F7（管理端增强 + 小程序首页配置）**。
2. **Figma 不再作为交付物**：以 HTML 原型（`docs/features/F6.0-membership-card-prototype/prototype/index.html`）为**唯一最终设计依据**，直接进入开发。
3. **F6.0 剩余决策按推荐方案采纳**：D2 不新增用尽状态 / D6 先过期优先 → 剩余次数少优先 → 同分取先发放 / D7 新增原子改期与原子改派端点 / D8 本版仅入口占位。至此 **F6.0 全部 10 项决策（D1–D10）冻结**，记录见 `docs/features/F6.0-membership-card-prototype/open-decisions.md`。

**下一步**：将 F6.0 拆分为可开发 Feature（F6.3+）写入 `feature-backlog.md`，按 `feature-delivery-lifecycle` 逐项交付；F7.0 保持设计冻结，暂不排期。

---

## 更新 2026-10-09：F6.0 会员卡业务原型规划（只读审计，未改业务代码）

> 产物目录：`docs/features/F6.0-membership-card-prototype/`（8 份规划文档：feature-inventory / business-rules / entity-state-model / cross-platform-user-flows / screen-inventory / interaction-spec / open-decisions / prototype-acceptance）

**当前阶段**：REQUIREMENT/PROTOTYPE-PLANNING —— 只读审计完成，原型规划文档就绪；等待产品负责人确认 D1-D8 决策后进入 Figma 原型制作。

**审计核心结论**（证据见 feature-inventory.md）：
- 预扣模式已固化：预约创建即扣次（同事务 CONSUME），签到/完成不扣次（booking/service.py:130-155, 275-332）——与"签到核销"直觉相反，原型按现状表达，D1 决策是否改为签到扣
- 卡状态机 5 态无"用尽"态（D2）；无首次核销激活（D1）
- 卡失效后既有预约零处理（D3）；原子改期/改派不存在（D7）；退款未实现（D8）
- 端能力差距：student-web 零会员卡能力；admin-web 无预约管理页；卡详情/流水页两端均缺（API 已备）
- order/payment/notification 为空壳（F6.1/F6.2 依赖）

**待确认决策**：D1 扣次时机（联动 D9，改为预扣+COMPLETED 确认）/ D2 用尽状态 / D3 失效替代 / D4 有效期边界（联动 D9，期卡从首次 COMPLETED 算）/ D5 缺席处理（联动 D9，自动消解）/ D6 多卡推荐 / D7 改期原子性 / D8 退款 / **D9 期限卡预约校验（首次 COMPLETED 激活 + 预期有效期冲突预校验，用户确认方案）**（推荐方案与影响见 open-decisions.md，需产品负责人逐项勾选；D1/D4/D5 随 D9 联动更新）

**后续 Agent 与交付依赖**：
1. 产品负责人 → 勾选 D1-D9（阻塞 Figma 制作中的占位固化）
2. UI/原型执行方 → 按 screen-inventory.md 15 个页面（P-A1~A6 / P-M1~M7 / P-T1）+ interaction-spec.md 制作 Figma；验收走 prototype-acceptance.md
3. backend-engineer（原型确认后）→ 新端点排期：原子改期/改派（D7）、受影响预约查询（D3）、缺席标记（D5）→ 应在 feature-backlog 新建 F6.3+ 条目
4. 下游 Epic 对接：F6.1 支付渠道（D8）、F6.2 通知（卡到期/预约提醒原型占位已预留）

**原型命名说明**：F6.0 为 Epic 6（业务域补全）的原型规划条目，不进入 feature-delivery-lifecycle 开发队列；其下游后端任务另行立项。

---

（以下为 2026-09-26 原始 Board 内容，部分状态已过时：Epic 1-5 各 Feature 与 F3.2/F3.3/F3.4 均已于 09-26~10-02 期间完成，实际状态以 docs/delivery/feature-backlog.md 验收结论为准）

> 角色：Feature Delivery Manager + Project Architect
> 输入：docs/delivery 5 份基线文档、docs/ai/skill-registry.md、F3.1 全套交付物、`.trae/rules/`、multi-agent-collaboration-v3.md、`.trae/skills/`，以及当日对真实代码的逐项核查
> 性质：**Backlog Analysis，未修改任何业务代码**
> 证据约定：所有结论带文件:行号证据；"未验证"项显式标 UNKNOWN，不做猜测

---

## Current State

- 已完成 Feature：**1 个**（F3.1）
- 真正 READY 可立即进入流水线：**9 个**（F1.2、F1.3、F1.4、F1.5、F2.3、F2.5、F4.3、F5.1、F5.3、F5.4 —— 其中 F1.4 带生产协调前置）
- BLOCKED：2 个（F2.1、F3.3）
- NEEDS_RECONCILIATION：4 个（F1.1、F2.2、F2.4、F5.2）
- NOT_READY：4 个（F3.2 带 1 个决策前置、F3.4、F4.1、F4.2、F4.4、F4.5 —— 共 6 个，见下表）
- FUTURE_PHASE：5 个（F6.1、F6.2、F7.1、F7.2、F7.3）

当日代码核查的关键事实：

| 事实 | 证据 |
|------|------|
| RBAC 仍全局放行 | `core/rbac/checker.py:39` `PERMISSION_CHECK_BYPASS = True`（硬编码，非环境变量） |
| 测试后门仍裸露 | `modules/common/router.py:46` `/test-exception`、`:85` `/test-token`，无装饰器 |
| 端点装饰器覆盖不全 | booking 7 端点/2 装饰器、teacher 3/0、tenant 2/0、common 5/0、ai 4/0、course 15/9、membership 23/15、schedule 8/6、classroom 5/3；role 8/8、user 9/10、admin 覆盖较全 |
| 登出只拉黑 refresh_token | `modules/auth/service.py:286`；`get_current_user` 无 `is_token_blacklisted` 调用（全 core 目录仅函数定义处 1 处匹配） |
| 无通用 Exception handler | `main.py:163-164` 仅注册 DanceSaasException + IntegrityError；`config.py:35` `APP_DEBUG: bool = True` |
| 生产 Redis 无密码 | `infra/docker/docker-compose.prod.yml:18-45` 无 requirepass，REDIS_URL 无密码 |
| 定时任务无租户循环 | `schedule/scheduler.py:11,37,98` 直接 `SessionLocal()`；全 modules 无 `set_tenant_id` 调用 |
| admin 用户管理仍是 Mock | `admin/service.py` 全文 TODO + 假数据（create id=9999、list total=100 硬编码） |
| 预约列表存在越权洞 | `booking/router.py:66` `student_id = current_user... if not schedule_id else None` —— 传 schedule_id 即不过滤；`get_booking_by_id`（service.py:321-331）零归属校验 |
| 签到/完成无行锁 | `booking/service.py:282,306` 均为普通 `get_by_id`（仅取消路径 L213 有 FOR UPDATE） |
| cancel_schedule 吞异常 | `schedule/service.py:283-291` restore_credit 外包 try/except |
| delete_schedule 跨层 | `schedule/router.py:211-229` 直接 `schedule_service.repo` + 实例化 BookingRepository |
| miniapp 无类型门禁 | `apps/miniapp/package.json:9` build 脚本无 vue-tsc；当前 **27** 个 TS 错误（Backlog 写"30+"，已过时） |
| 两处外键缺失仍在 | `booking/models.py:52`、`order/models.py:58` membership_card_id 均无 ForeignKey |
| status Check 约束不存在 | 仅有 chk_schedule_time/capacity、chk_credits_range；bookings/course_schedules/membership_cards 的 status 均无 Check |
| AI 排期格式确实断裂 | `mcp_server.py:161-165` 输出 `- MM/DD HH:MM 课程 教师：x 教室：x 已约：a/b（排期ID: n）`；`runtime.py:485-486` 正则要求 `- ID:n | YYYY-MM-DD | HH:MM-HH:MM | 师 | 剩余:n` —— 永不命中，`_parse_schedules` 必返回 [] |
| AI 异常映射失效 | `runtime.py:348` `str(error).upper()` 匹配英文 key（SCHEDULE_FULL 等），业务异常实际为中文（如"名额已满"），映射永不命中 |
| ai/tools 零引用 | 全 app 无 `ai.tools` import；目录内 11 个历史文件仍在 |
| MCP 写工具鉴权现状 | `mcp_server.py:279,312` 有 `_require_auth`（认证）；create/cancel 强制 `student_id=user_id`，归属由 service.py:175 兜底；但无显式"必须是学员角色"判断 |

---

## Done Features

| Feature | 关闭日 | 交付物 | 遗留 |
|---------|--------|--------|------|
| F3.1 miniapp 运行时崩溃修复 | 2026-09-26（人工验收通过） | docs/features/F3.1-miniapp-crash-fix/ 9 份文档 | D-F3.1-3（学员页预存改动归属）待用户决策；6 项 H5 环境 UNKNOWN 已由人工验收覆盖 |

F3.1 **不再进入任何开发队列**。

---

## Ready Features

无需补前置、AC 可验证、可立即进入 feature-delivery-lifecycle 流水线：

| Feature | Phase | 风险级 | 闭环方式 | 备注 |
|---------|-------|--------|---------|------|
| **F1.2 JWT Token 主动失效** | 1 / P0 | 安全（中） | login→logout→旧 token 401，curl 即可闭环 | 3 个小任务，无设计成本，**首选下一项** |
| F1.3 通用异常处理器 + debug 关闭 | 1 / P0 | 安全（低） | 构造异常验证信封 + traceback 不泄露 | T1.3.3 AI router 异常属性修正需一并核 |
| F1.5 定时任务租户隔离 | 1 / P0 | 数据隔离（中） | 多租户数据下跑 scheduler 集成测试 | membership/scheduler.py 同样在 Scope（Backlog 文字只点名 schedule/membership，需确认两文件都改） |
| F5.1 多轮预约流程修复 | 1 / P0 | 业务功能（中） | 已有 `tests/test_multi_turn_booking.py` + 端到端对话 | 必须先定 T5.1.1 统一格式契约（设计产物，Feature 内部完成） |
| F5.3 AI 异常处理不泄露 | 1 / P1 | 安全（低） | 触发中文业务异常验证友好映射 + 兜底 | 机制已确认失效，任务与代码一致 |
| F2.3 签到/完成行锁 | 1 / P1 | 并发数据一致（中） | 复用取消路径的 FOR UPDATE 模式 + 并发测试 | 模式已有先例（service.py:213） |
| F2.5 delete_schedule 下沉 Service | 2 / P1 | 低 | 端点行为不变回归 | 纯分层整改，注意保持现有 403 装饰器 |
| F4.3 解冻批量操作锁排序 | 2 / P1 | 并发死锁（低） | 代码级 + 并发测试 | 改动一行 `sorted()` + 调用顺序；设计阶段需先确认 `conflict_card_ids` 当前形态 |
| F5.4 清理 ai/tools/ 残留 | 2 / P2 | 极低 | import 零引用已核实；删除后跑全量后端测试 + AI 回归 | 删除型任务，用 minimal-change-guard 反查 |
| F1.4 生产 Redis 密码 | 1 / P0 | **生产环境（高）** | 本地 compose 验证；生产发布需停机/滚动窗口 | 需运维协调 REDIS_PASSWORD 注入；T1.4.3 目标文件 `.env.prod.example` 是否存在未核（UNKNOWN） |

---

## Blocked Features

| Feature | 阻塞项 | 解除条件 |
|---------|--------|---------|
| F2.1 admin 用户管理真实化 | 显式依赖 F1.1（RBAC 真实生效）——真实：在 BYPASS=True 下把 Mock 换成真实写操作等于裸奔 | F1.1 关闭（装饰器覆盖 + bypass=False） |
| F3.3 admin tenant 页对接 | `PUT /tenant/settings` 不存在（tenant/router.py 仅有 GET /settings、GET /info）；Backend 必须先行 | 先做 T3.3.1（本 Feature 内的后端任务），但 Backlog 依赖字段误写为"Feature 2.x"（该 Feature 不存在）→ 先 Reconciliation 再开工 |

---

## Needs Reconciliation

### R1 — F1.1 RBAC 真实生效

| 项 | 内容 |
|---|---|
| Conflict | ① Backlog 把"bypass 置 False"列为 T1.1.1（第一步），该顺序在装饰器未补齐时会立即锁死正常用户；② T1.1.4"补 RBAC 集成测试"——测试已存在（`tests/integration/test_rbac.py`、`test_rbac_real_redis.py`、`test_tenant_isolation.py`、`test_auth_api.py`），任务是"扩覆盖"而非"新建"；③ 9 个 router 110 个端点的装饰器缺口没有权限矩阵作为施工依据；④ AC"所有写操作端点有装饰器"与 auth（login/register/refresh）、common、ai/chat 的公开/半公开语义冲突，需逐端点政策 |
| Evidence | checker.py:39；端点/装饰器计数表；common/router.py:46,85；tests/integration/ 目录 |
| Impact | 不加矩阵直接翻开关 = 全站可用性事故；矩阵正是 skill-registry 中 S7（Planned）的场景 |
| Recommendation | 调整任务顺序：**T0 权限矩阵（S7 pilot）→ 补装饰器 → 扩测试（含 test-token 用例）→ 处理 common 后门 → 最后翻 bypass=False（改环境变量默认值）**。Reconciliation 可在本 Feature 的 REQUIREMENT/DESIGN 阶段完成，不需要先开别的 Feature |

### R2 — F2.2 预约归属（已部分完成且仍有洞）

| 项 | 内容 |
|---|---|
| Conflict | T2.2.1 描述的 list 过滤"看似已做"（router.py:66 有 student_id 注入），但 `if not schedule_id` 开了旁路：学员带 schedule_id 即可看该排期全部预约；T2.2.2 详情归属校验完全未做（service.py:321）；T2.2.3 教师视角无角色模型支撑（当前 token 内无角色分支） |
| Evidence | booking/router.py:66；booking/service.py:321-331 |
| Impact | 真实越权读取（P1 描述，实际漏洞在线）；教师端功能也依赖同一角色判断 |
| Recommendation | 重写 Scope/Tasks：①list 对非管理角色强制归属且不允许 schedule_id 旁路；②detail 归属校验；③先确认角色判定来源（platform_role vs RBAC roles），这是本 Feature 的隐式前置设计；④补越权集成测试（A 学员 token 读 B 预约 → 403/404） |

### R3 — F2.4 回滚语义自相矛盾

| 项 | 内容 |
|---|---|
| Conflict | T2.4.2"失败预约记录到 failed_bookings **但事务回滚**"——同一事务回滚后插入的记录也会回滚，物理上不成立 |
| Evidence | schedule/service.py:273-296 |
| Impact | 实施时会产生"先吞异常再手工补偿"的错误实现 |
| Recommendation | 二选一并写入 AC：A) 任一回补失败整体回滚、错误上抛（最简，符合 Goal）；B) 需要失败留痕则引入独立事务/outbox 或日志表（另开 Feature）。建议选 A，failed_bookings 留痕移出本 Feature |

### R4 — F5.2 Tool 授权（大部分已结构性满足）

| 项 | 内容 |
|---|---|
| Conflict | Backlog 暗示授权完全缺失；实际认证（_require_auth）与归属（student_id 强制注入 + service.py:175 归属校验）已存在；缺的是显式角色判断（教师能否通过 AI 为学员代约？产品语义未定义） |
| Evidence | mcp_server.py:279-289,312-322；booking/service.py:175 |
| Impact | 若直接按 Tasks"加授权"可能重复造校验、与 Service 层规则分叉（违反 ai/mcp.md 的 Tool→Service 边界） |
| Recommendation | 先做一次代码级 gap 确认（可作为 Feature 立项前的轻量分析），大概率只补"角色策略"与测试，而非实现新校验链 |

---

## Future Phase

| Feature | 目标 Phase | 当前状态说明 |
|---------|-----------|-------------|
| F3.4 前端四态补全 | Phase 2 | NOT_READY：Scope 是"所有缺失页面"但无页面清单与验收标准，三端+小程序范围巨大；需先出逐页 inventory 再拆子 Feature |
| F4.1 bookings 外键 | Phase 3 | NOT_READY：需先审计并清理孤立 membership_card_id（数据前置，非 Feature 依赖）；生产数据风险，需要回填脚本与回滚预案 |
| F4.2 orders 外键+索引 | Phase 3 | NOT_READY：同 F4.1，需孤立数据审计 |
| F4.4 status Check 约束 | Phase 3 | NOT_READY：加约束前必须验证存量数据无非法状态值（数据审计前置） |
| F4.5 排期创建并发 | Phase 3 | NOT_READY：两种方案（同事务 vs SERIALIZABLE）需影响分析与性能评估后再选 |
| F6.1 支付渠道 | Phase 3+ | FUTURE_PHASE：业务域新建，依赖订单模型决策 |
| F6.2 通知系统 | Phase 3+ | FUTURE_PHASE：需微信订阅消息资质/模板 |
| F7.1 备份 / F7.2 监控 / F7.3 CI | Phase 5 | FUTURE_PHASE：运维能力建设 |

另：F3.2 虽属 Phase 2 且技术上 READY，但有 1 个**决策前置**：D-F3.1-3（student/schedule/index.vue 预存改动归属）必须先由用户决定，否则类型清零的提交会再次污染 diff。

---

## Dependency Graph

```
                       [S7 权限矩阵 artifact]  (skill-registry 登记为 Planned，F1.1 内部产出)
                                  │
                                  ▼
   F1.1 RBAC ─────────────────────┴──────────────► F2.1 admin 真实化
     │（后门/装饰器/矩阵/翻开关）
     ├─(安全基线，无强依赖但建议先于)─► F2.2 预约归属(需 R2 角色设计)
     └─(安全基线)────────────────────► F5.2 Tool 角色策略(R4)

   F1.2 JWT 黑名单          [独立，仅依赖 Redis]
   F1.3 异常+debug=False    [独立]
   F1.4 Redis 密码          [独立；依赖生产运维窗口]
   F1.5 scheduler 租户隔离  [独立；依赖多租户测试数据]

   F2.3 签到/完成行锁        [独立；复用已有 FOR UPDATE 模式]
   F2.4 cancel 回滚          [需先 R3 语义裁决]
   F2.5 delete 下沉 Service  [独立]
   F4.3 锁排序               [独立；一行改动]

   F3.1 ✅ DONE
   F3.2 类型门禁             [前置：用户对 D-F3.1-3 的决策]
   F3.3 admin tenant 页      [前置：T3.3.1 后端 PUT（Backlog 依赖标注错误，需更正）]
   F3.4 四态                 [前置：逐页 inventory]

   F5.1 多轮预约             [内部前置：T5.1.1 统一排期格式契约]
   F5.3 异常映射             [独立]
   F5.4 删 ai/tools          [独立；零引用已核实]

   F4.1/F4.2 外键            [前置：孤立数据审计+回填脚本] ── 数据库依赖
   F4.4 Check 约束           [前置：存量状态值审计]        ── 数据库依赖
   F4.5 排期并发             [前置：方案影响分析]          ── 数据库依赖
```

依赖类型说明（均经代码核查，非照抄 Backlog）：

- **显式依赖**：F2.1→F1.1（真实且必要）
- **隐式代码依赖**：F2.2 的教师视角依赖角色判定来源（R2）；F5.1 格式契约横跨 mcp_server.py 与 runtime.py（同 Feature 内两个文件必须同批改）
- **数据库依赖**：F4.1/F4.2/F4.4 均以存量数据审计为前置；F4.5 涉及隔离级别选择
- **API 契约依赖**：F3.3 依赖尚不存在的 `PUT /tenant/settings`（OpenAPI 是唯一契约源，前端不得先写调用）
- **权限依赖**：F2.1 真实写操作必须在 F1.1 之后；F5.2 依赖角色策略定义而非 HTTP RBAC
- **测试环境依赖**：后端 Feature 均可使用现有 Docker PG+Redis 与 tests/integration；F1.5/F4.x 还需多租户/并发数据夹具；F5.1 端到端依赖 LLM 响应，需以确定性夹具或 mock runtime 保证可重复
- **工件依赖**：F1.1 依赖权限矩阵（S7）；F3.4 依赖页面清单

---

## Next Feature Decision

**推荐：F1.2 JWT Token 主动失效**

决策矩阵对比（READY 候选中）：

| 因素 | F1.2 | F5.1 | F1.1 | F3.2 |
|------|------|------|------|------|
| 当前状态 | READY | READY | NEEDS_RECONCILIATION | READY（带决策前置） |
| 风险类型 | 安全（token 重放） | 业务功能断裂 | 安全+全站可用性 | 代码质量 |
| 解除他人依赖 | 无直接 | AI 系列 | F2.1 + 安全基线 | 无 |
| Phase | 1/P0 | 1/P0 | 1/P0 | Phase 2 |
| AC 完整性 | 单行、确定性 | 完整但端到端含 LLM 不确定性 | 需矩阵后才可验证 | 完整 |
| 验证闭环 | 3 步 curl 即可判定 | 需 mock/夹具固定 LLM 输出 | 需逐端点 403 矩阵测试 | vue-tsc 计数 |
| 实施风险 | 低（3 个小任务，黑名单函数已存在） | 中（契约改动牵动 prompt/解析/输出） | 高（翻开关影响全站） | 低但繁琐（27 错误） |
| 前置条件 | 无 | 需先定格式契约 | 矩阵+装饰器+测试 | D-F3.1-3 决策 |

**为什么是 F1.2 而不是 ID 最小/列表最前的 F1.1**：F1.1 是价值最大的安全 Feature，但当前状态是 NEEDS_RECONCILIATION——在权限矩阵产出前翻 bypass 开关有全站锁死风险，正确做法是先完成它的矩阵/排序对账再开工；F1.2 无任何前置、改动小、闭环确定性最高、且能立刻消除"登出后 2h 内旧 token 仍可用"的真实安全洞。同时它是新建 3 个 Skill 后第一个复用 S1 全流程的后端 Feature（与 F3.1 的前端样本形成互补验证）。

## Execution Order

建议节奏（可按 Agent 空闲并行；同列任务无文件冲突）：

| Wave | 主轨（backend） | 旁轨 | 准出 |
|------|----------------|------|------|
| W1 | **F1.2** JWT 黑名单 | **F3.2**（先决策 D-F3.1-3；frontend-engineer） | 401 闭环；vue-tsc=0 + build gate |
| W2 | F1.3 异常处理；F5.4 删 ai/tools/ | F5.3 AI 异常映射（mcp-engineer） | 标准化 500；AI 中文异常命中友好提示 |
| W3 | **F1.1**（先完成 R1 矩阵对账再实施；本 Wave 周期最长） | F1.5 scheduler 租户隔离 | bypass=False 且全矩阵 403 测试绿 |
| W4 | F2.1（解锁）+ F2.3 + F2.5 + F4.3 三个小整改串行/并行 | F5.1（先定格式契约，mcp-engineer） | admin 真实化；并发安全；AI 完整预约 |
| W5 | R2 对账后的 F2.2；R3 裁决后的 F2.4；R4 对账后的 F5.2 | F1.4（按运维窗口择期） | 越权闭环 |
| W6 | F3.3（后端 PUT 先行）→ Phase 1 准出复评 | F3.4（先 inventory 再拆） | Phase 1 关闭 |
| Phase 3 | F4.1/F4.2（数据审计后）→ F4.4 → F4.5 | | |
| Phase 5 | F7.x；F6.x 按业务优先级另排 | | |

每个 Feature 一律走 `.trae/skills/orchestration/feature-delivery-lifecycle/`；最小修改类（F5.4、F4.3、F1.2）强制 minimal-change-guard；miniapp 相关走 miniapp-runtime-smoke-test。

## Risks

1. **F1.1 翻开关顺序风险（最高）**：必须矩阵→装饰器→测试→最后翻 bypass；建议灰度（先在测试环境用真实角色全矩阵跑一遍）。
2. **F2.2 漏洞在线**：在 W5 之前学员可越权读取他人预约；如风险窗口不可接受，可把 R2 对账+最小封堵（仅补 detail 归属 + 去掉 schedule_id 旁路）提前到 W2 作为热修。
3. **F1.4 生产变更**：requirepass 上线需要应用与 Redis 同步切换，错误顺序导致全量缓存/黑名单不可用；必须有人工发布步骤。
4. **F4.x 数据型迁移**：外键/Check 约束在脏数据上直接加会锁表或失败；必须先只读审计。
5. **F5.1 LLM 不确定性**：端到端验收需固定模型输出或在 runtime 层加可测解析入口，否则 AC 无法稳定复现。
6. **工作区卫生**：当前存在 F3.1 之外的大量历史未提交改动（RBAC、AI、membership 等文件）；任何 Feature 开工前必须先跑 minimal-change-guard 的修改前检查并冻结白名单。
7. **F1.5 测试夹具**：多租户 scheduler 测试需要至少 2 个 ACTIVE 租户数据，现有夹具是否支持未核（UNKNOWN）。

## Backlog Issues

需要修正文档的条目（本阶段未改 Backlog，仅登记）：

| # | Feature | 问题 | 建议修正 |
|---|---------|------|---------|
| B1 | F1.1 | Tasks 顺序不安全；T1.1.4 测试已部分存在；缺权限矩阵任务；公开端点政策未定义 | 按 R1 重排任务、把 T1.1.4 改为"扩展现有 RBAC 测试覆盖" |
| B2 | F2.2 | 已部分完成且旁路仍在；Tasks 未反映现状；缺角色来源设计 | 按 R2 重写 Scope/Tasks/AC |
| B3 | F2.4 | T2.4.2 与事务回滚语义矛盾 | 按 R3 裁决后修正 |
| B4 | F3.2 | "30+ TS 错误"已过时（实测 **27**，分布已记录）；应显式纳入 D-F3.1-1/2/4 | 更新数字与任务清单；开工前挂 D-F3.1-3 决策 |
| B5 | F3.3 | Dependencies 写"Feature 2.x"，该 Feature 不存在；PUT 端点是自己的 T3.3.1 | 改为"内部后端任务先行"，或拆出独立后端 Feature |
| B6 | F5.2 | 与代码现状不符（认证+归属已存在） | 按 R4 改为"角色策略 gap 确认 + 补测试" |
| B7 | F1.5 | Scope 文字只说 schedule/membership scheduler，需明确文件清单（含 membership/scheduler.py） | REQUIREMENT 阶段列文件白名单 |
| B8 | F3.4 | 无 AC、无 Out of Scope、无页面清单 | 立项前必须补 inventory，再拆子 Feature |
| B9 | F1.4 | `.env.prod.example` 是否存在未核（UNKNOWN） | REQUIREMENT 阶段先核实目标文件 |
| B10 | F4.1/F4.2 | "先清理孤立数据"未明确审计 SQL 与备份要求 | DESIGN 阶段产出审计脚本（只读）+ 备份/回滚预案 |
