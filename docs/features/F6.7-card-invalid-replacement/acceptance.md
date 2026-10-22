# F6.7 验收标准：卡失效替代与受影响预约（D3）

> 日期：2026-10-22。M5 测试分层：A 静态 / B 单元 / C 集成 / D 前端 / E 权限 / F 人工验收。
> 测试夹具复用 `apps/api/tests/membership_support.py`（`create_card/create_booking/future_start/db_factory/login/headers` 等）。

## A. 静态验收

| # | 项 | 标准 |
|---|----|------|
| A-1 | `py_compile` | 改动 .py 全部通过 |
| A-2 | `ruff`（改动文件） | 0 error |
| A-3 | 路由注册 | `GET /api/v1/membership/cards/{card_id}/affected-bookings` 出现在 OpenAPI；无尾斜杠变体 |
| A-4 | 契约生成 | `pnpm gen:types` 通过；`packages/api-types` 产物含新端点；产物无手改 |
| A-5 | 前端类型 | admin-web `vue-tsc -b && vite build` 通过；miniapp `vue-tsc` + `build:mp-weixin` 通过 |
| A-6 | 分层审查 | Repository 不做业务决策；Router 无业务判断；跨模块仅经 Service（booking↔membership 无 Repository 直调、无循环 import） |
| A-7 | 权限声明 | 新端点虽不挂 `@require_roles`（混合角色），但 Service 内有显式 `check_roles` + 归属校验（代码审查项） |

## B. 单元测试（Service/纯逻辑层，DB 直连夹具）

| # | 用例 | 预期 |
|---|------|------|
| B-1 | 口径：BOOKED + 未来 start_at | 计入 total 与 items |
| B-2 | 口径：CHECKED_IN + 未来 start_at（夹具直改 booking.status=3） | 计入 |
| B-3 | 口径：CANCELLED / COMPLETED / NO_SHOW + 未来 start_at | 不计入 |
| B-4 | 口径边界：start_at <= now（含过去与刚好等于） | 不计入（R-1 严格大于） |
| B-5 | 口径边界：start_at 为当天稍晚未来时刻 | 计入（R-3） |
| B-6 | 口径：他卡预约 / 无卡预约（membership_card_id IS NULL） | 不计入 |
| B-7 | 归属：student 查本人卡 | 放行 |
| B-8 | 归属：student 查同租户他人卡 | `PermissionException`（403） |
| B-9 | 归属：admin / super_admin 查本租户任意卡（含他人卡） | 放行 |
| B-10 | 卡不存在 | 404 |
| B-11 | 排序：多预约返回按 `start_at ASC, id ASC` | 次序稳定 |
| B-12 | 分页：total 跨页正确、items 切片正确；page_size>100 被 Pydantic 拒绝 | — |

## C. 集成测试（HTTP 契约，TestClient + 种子租户）

| # | 用例 | 预期 |
|---|------|------|
| C-1 | admin token 查本租户卡，卡有 BOOKED×2（未来）+ COMPLETED×1 + CANCELLED×1 | 200，`total=2`，items 仅含未来 BOOKED |
| C-2 | student 查本人卡 | 200，字段齐全（card_id/card_status/total/items） |
| C-3 | student 查同租户他人卡 | 403，信封 `{code,msg}`，无 traceback |
| C-4 | 跨租户：用租户 A 的卡 id + 租户 B 的 token/slug | 404（租户隔离，不泄露存在性） |
| C-5 | 未认证 | 401 |
| C-6 | 卡不存在（本租户内） | 404「会员卡不存在」 |
| C-7 | CHECKED_IN + 未来排期 | 计入 items，`status=3` |
| C-8 | 排期 start_at 已过（昨天）+ BOOKED | 不计入 |
| C-9 | 分页参数 `page=2&page_size=1`（total=2 时） | 返回第 2 条；`page_size=0`/`101` → 400 |
| C-10 | 冻结后语义验证：先 freeze 卡 → 再查 affected-bookings | 仍返回相同 N（查询只读、与卡状态无关，R-8）；`card_status=3` |
| C-11 | **并发专项（M5 保留项）：作废 vs 改派竞态** | 见 §C-并发 |
| C-12 | **并发专项：冻结 vs 改派竞态** | 见 §C-并发 |

### C-并发（竞态设计，至少落地 1 条，优先 C-11）

```
前置：学员有卡 C（ACTIVE）+ 卡 D（ACTIVE 可替代）+ 预约 B（BOOKED，未来，用卡 C）
线程1：admin POST /cards/{C}/cancel（或 freeze）
线程2：student POST /bookings/{B}/reschedule { new_schedule_id: B.schedule_id, new_membership_card_id: D }
断言（两者均完成后）：
  - 无死锁、无 500；两请求各自得到确定结果（200/400/409）
  - 若改派先提交：B.membership_card_id == D，C 作废成功；最终 B 不再受影响（affected-bookings(C).total == 0）
  - 若作废先提交：改派要么成功（回补/扣次按 F6.5 语义完成，旧卡已作废不阻断回补）要么 400/409；
    无论哪条路径，B 不得处于「卡已扣次但预约仍指向作废卡 C 且 D 也被扣次」的双扣/悬空状态
  - 账务守恒：D 扣次次数 ∈ {0,1}，C 回补次数 ∈ {0,1}，无双扣双补
```

> 说明：F6.5 锁序为 advisory→booking→schedule→card(id ASC)，`cancel_card` 仅持 card 锁（`service.py:2202`），锁序兼容无环；本用例验证的是「结果可解释 + 账务守恒」，不强制两请求的相对先后。

## D. 前端验收

| # | 端 | 用例 | 预期 |
|---|----|------|------|
| D-1 | admin | 冻结弹窗打开时自动查询影响面 | total>0 显示「该卡有 N 个有效预约」+ ≤5 条明细（课程/时间/状态） |
| D-2 | admin | 作废弹窗同上（文案含「不可恢复」提示） | — |
| D-3 | admin | total=0 | 中性提示「该卡无受影响预约」 |
| D-4 | admin | 影响面查询失败（断网/500 mock） | 错误条 + 重试；冻结/作废按钮仍可用（R-7 不阻断） |
| D-5 | miniapp | 预约列表中卡已冻结/过期/作废的 BOOKED 预约 | 警示条（区分三种卡状态文案）+「换卡」按钮 |
| D-6 | miniapp | CHECKED_IN + 卡失效 | 仅警示条「请联系机构处理」，无换卡按钮 |
| D-7 | miniapp | 换卡全流程：选卡弹层默认选中推荐卡 → 确认 → 改派成功 | toast + 列表刷新，原预约卡已替换 |
| D-8 | miniapp | 改派 400/409（如目标卡恰好失效） | 展示后端 msg，停留弹层可重选 |
| D-9 | miniapp | 无替代卡空态 | 「暂无可用替代卡」+「联系机构」引导，无死路 |
| D-10 | miniapp | 无失效卡 | 不渲染任何警示（回归保护） |
| D-11 | 四端契约 | 不调用未交付端点；类型来自 api-client/api-types | grep 核对 + gen:types 一致 |

## E. 权限验收（RBAC 矩阵实测）

| # | 角色 | 本人卡 | 他人卡（同租户） | 跨租户卡 |
|---|------|--------|------------------|----------|
| E-1 | admin / super_admin | 200 | 200 | 404 |
| E-2 | student | 200 | 403 | 404 |
| E-3 | teacher | 403（视同非本人，除非恰好是本人卡） | 403 | 404 |
| E-4 | 未认证 | 401 | 401 | 401 |
| E-5 | `PERMISSION_CHECK_BYPASS` 债务不扩散 | 新代码不新增 bypass 开关、不依赖现存 bypass 行为 | — | — |

## F. 人工验收清单

1. admin 对一张有 3 个未来预约的冻结卡执行冻结：弹窗 N=3 与明细准确；冻结成功后学员小程序看到警示。
2. 学员用另一张有效卡自助换卡成功；admin 再次查询该作废/冻结卡 affected-bookings，N 相应减少。
3. 学员无替代卡：空态与「联系机构」引导展示正确。
4. 学员尝试查询他人卡 affected-bookings（改请求）：403。
5. 作废有预约的卡：admin 弹窗警示文案准确，确认后卡作废、预约保留（不自动取消）。
6. 回归：my-cards、预约列表、recommend-card、改派（F6.5 既有路径）无回归。
