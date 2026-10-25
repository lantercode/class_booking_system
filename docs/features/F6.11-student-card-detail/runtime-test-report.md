# F6.11 运行时测试报告

> 日期：2026-10-25。测试对象：真实后端 :8000 接口 + 浏览器 localhost:5174（student-web）+ 双端构建。
> 原则：未执行项统一标记 **NOT VERIFIED**，不写成通过。

## 1. 后端真实接口冒烟（已验证）

| # | 场景 | 预期 | 结果 |
|---|------|------|------|
| R-1 | 学员本人卡详情 | 200 | ✅ |
| R-2 | 学员他人卡详情 | 403 | ✅ |
| R-3 | 学员他人卡流水（传他人 `card_id`） | 403 | ✅ |
| R-4 | 学员列表传他人 `student_id` | 403 | ✅ |
| R-5 | 不存在卡（含跨租户） | 404 | ✅ |
| R-6 | admin 任意卡详情 | 200 | ✅ |
| R-7 | admin 全租户流水 | 200 | ✅ |
| R-8 | 学员不传 `card_id` 流水 | 仅本人卡：`distinct card_id ⊆ 本人卡` | ✅ |

## 2. 构建（已验证）

| 命令 | 结果 |
|------|------|
| `pnpm --filter dance-miniapp build:mp-weixin` | ✅ `vue-tsc --noEmit` 通过 + `DONE Build complete.` |
| `pnpm --filter student-web build` | ✅ `✓ built in 4.15s`，产物含 membership/detail/transactions 分包 |

## 3. 浏览器实测（已验证，student-web localhost:5174）

| # | 场景 | 预期 | 结果 |
|---|------|------|------|
| B-1 | 学员 13900139001 打开 `/membership` | 渲染 6 张卡 | ✅ |
| B-2 | Tab 切换 | 全部/可用/不可用切换生效 | ✅ |
| B-3 | 点击卡片进入 `/membership/1934` | 卡号/状态/课时正确，接口 200 | ✅ |
| B-4 | 打开他人卡 `/membership/1932` | 「无权查看该会员卡」+ 返回列表/重试，接口 403 | ✅ |
| B-5 | 打开不存在卡 `/membership/999999` | 「会员卡不存在或已失效」 | ✅ |
| B-6 | 控制台 | 无 Vue 运行时错误 | ✅ |

## 4. 未验证（NOT VERIFIED）

以下项未执行或未取得运行证据，**不得视为通过**：

| # | 项 | 状态 | 说明 |
|---|----|------|------|
| N-1 | 微信开发者工具/真机滚动续页（`onReachBottom`） | **NOT VERIFIED** | 仅构建通过，未在开发者工具/真机验证 |
| N-2 | 流水页在浏览器中的实测截图 | **NOT VERIFIED** | 构建与代码审查通过，未做 UI 点击实测 |
| N-3 | student-web 服务端状态筛选 | **NOT VERIFIED** | 当前为前端 Tab 分组，未实现服务端筛选 |

> 另：miniapp 的 403/404 文案分支仅经代码审查确认，未在真机走通。

## 5. 回归

| # | 项 | 结果 |
|---|----|------|
| 1 | `test_membership_affected_bookings.py` | ✅ 24 passed |
| 2 | `test_card_recommendation.py` | ✅ 9 passed |
| 3 | admin-web 会员卡/流水（admin 分支） | ✅ 契约与行为未变，未做 UI 实测 |
| 4 | miniapp 激活/解冻/复制卡号 | ✅ 代码审查确认 `@tap.stop` 保留；未做真机实测 |

## 6. 人工验收结论

**未完成**。可复现部分（列表、Tab、详情、403、404、控制台）已通过；真机续页与流水 UI 需人工补验后签字。
