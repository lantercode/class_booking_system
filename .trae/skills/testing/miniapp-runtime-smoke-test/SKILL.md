---
name: miniapp-runtime-smoke-test
description: 对 apps/miniapp 页面做运行时冒烟验证并输出结构化报告，覆盖加载崩溃、数据加载、空错态、降级、认证拦截与控制台异常。当 miniapp 代码改动后或 Feature 运行时验收门控需要时使用。不用于静态类型检查或构建验证。
---

# Miniapp Runtime Smoke Test

验证小程序页面在运行时**不崩溃、流程可走通、异常被正确处理**。本 Skill 定义验证方法与记录规范；当前项目用 H5 + 浏览器作为执行载体，具体启动/取 token/注入方式是项目实现细节，见 `scripts/` 与 F3.1 实例。

首个完整样板：`docs/features/F3.1-miniapp-crash-fix/runtime-test-report.md`。

## When to Use

- miniapp（`apps/miniapp/`）任何页面/组件/请求层改动后的运行时回归
- Feature 流水线阶段 9（TESTING），acceptance.md 中含运行时类 AC
- P0 崩溃类修复的验收

**Do Not Use**：vue-tsc 类型检查、`uni build` 构建验证（属 minimal-change-guard 的静态环节）；Web 三端（admin/student/teacher-web）的浏览器验证。

## Inputs

- 目标页面路由清单（取自 `apps/miniapp/src/pages.json`）+ 每页重点验证点
- acceptance.md 中运行时类 AC 编号
- 可用测试账号（手机号/密码）与租户 slug；无账号时先通过 API 注册（见 scripts）
- 预期的环境限制清单（H5 与微信原生能力的差异，需提前声明而非事后解释）

## 结果词表（固定，禁止"基本通过"）

| 结果 | 定义 |
|------|------|
| PASS | 观察到的实际行为与 Expected 一致 |
| FAIL | 观察到与 Expected 冲突的行为（崩溃、错误提示、数据错误） |
| BLOCKED | 环境/工具/账号原因无法执行该用例（不是缺陷判定） |
| UNKNOWN | 用例部分可验但保真度不足（如 H5 无法复现原生视觉/时序） |
| NOT TESTED | 尚未执行（最终报告中不允许残留，须转成上述四种之一并说明） |

## 每条用例的最小记录字段

Test Case / Preconditions / Steps / Expected / Actual / Result / Evidence / **Verified By**（自动化工具名或人工）/ **Environment**（H5 或微信开发者工具+版本）/ **Timestamp**。

报告骨架见 `templates/runtime-test-report.md`。

## Process

1. **明确范围**：页面清单 + 每个页面的崩溃敏感点（未定义符号、onMounted 调用链、try/catch 边界），从 acceptance.md 映射用例编号。
2. **环境准备**：执行 `scripts/up-smoke-env.sh`（幂等：已运行的端口不重复拉起）。后端配置以 `apps/api/src/app/core/config.py` 默认值为准，不要假设命令。
3. **构建先行**：`apps/miniapp` 下 `npm run build:mp-weixin`，构建失败则本 Skill 直接终止（静态门未过，不做运行时）。
4. **取得身份**：H5 无微信授权登录链路，用 `POST /api/v1/auth/login`（body 带 `tenant_slug`，头带 `x-tenant-slug`）取 token；账号不存在则走 `/auth/register`。
5. **注入身份**：uni H5 的 storage 底层是 localStorage，注入页面代码实际读取的键（先查 `apps/miniapp/src/api/index.ts` 与 `utils/auth.ts` 确认真实键名，禁止凭记忆）。
6. **逐页验证**（浏览器自动化或人工），每页至少覆盖：
   - 加载无 ReferenceError / 白屏红屏
   - onMounted 链路完整（日志序列、数据区域渲染）
   - Loading / 空数据 / 错误 toast
   - 控制台 error 级别清扫（区分 ReferenceError / 网络错误 / 其他）
7. **横切场景**：
   - 未登录访问 → checkLogin 拦截、toast、回跳，页面不崩
   - 无效/过期 token → API 401 与前端拦截器行为
   - 角色不匹配 → 权限提示与回跳
   - 配置/网络失败降级（需要 Network 面板或拦截；H5 无法精确复现的降级时序标 UNKNOWN 并给微信开发者工具复现步骤）
   - 组件在异步返回前销毁（isUnmounted 路径）
8. **API 直测补位**：页面级难以稳定构造的认证/状态码场景，用 curl 直测 API 取证（如 401/403/200）。
9. **汇总**：按词表判定每组 AC，统计 PASS/FAIL/BLOCKED/UNKNOWN，写明环境限制，输出报告到 Feature 目录。

## 环境保真度原则

- H5 与微信开发者工具共享 Vue 运行时与 import 图，**ReferenceError 类崩溃、JS 调用链、localStorage 拦截行为等价**，可在 H5 判定。
- 以下必须标注为 H5 限制并转人工（微信开发者工具）：原生组件视觉呈现、需要精确网络时序的降级、微信授权链路、小程序专属 API。
- UNKNOWN 必须附"下一步如何验证"，不得作为放过缺陷的通道。

## 判定规则

- 出现任何目标缺陷相关的运行时错误（如待修复的 ReferenceError）→ FAIL
- 0 FAIL 且环境限制项均有替代证据/人工复核路径 → 可判运行时门 PASS
- 报告残留 NOT TESTED → 报告本身不合格

## 边界

- 不修改业务代码；发现新缺陷只记录（必要时登记技术债，交回生命周期 Skill）
- 不把 H5/browser/curl 当作方法论本体——它们是当前项目实现，换工具时验证方法不变
- 脚本只做环境拉起与只读探测，不执行数据清理、不重置数据库
