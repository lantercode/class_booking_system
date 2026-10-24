# F3.2 — 运行时验证报告（构建门禁正反两组）

> 日期：2026-09-29 ｜ 执行：frontend-engineer
> 工作目录：`apps/miniapp`
> 环境：macOS，node/npm（仓库已安装 vue-tsc 2.2.x / @dcloudio uni-app 3.0.0-4020920240930001）
> 说明：本 Feature 不改变任何页面运行时逻辑，运行时验证对象为**构建门禁的 shell 行为**（退出码 + `&&` 短路 + 产物）。

## 1. 验证矩阵

| # | 用例 | 前置 | 命令 | 预期 |
|---|------|------|------|------|
| RT-1 | 正向构建 | vue-tsc 0 error | `npm run build:mp-weixin` | vue-tsc 通过 → uni build 执行 → `DONE Build complete.`，退出码 0，产物更新 |
| RT-2 | 反向门禁 | 注入 1 个 TS 错误 | `npm run build:mp-weixin` | vue-tsc TS2322、退出码 2、uni build 不执行、无"正在编译中" |
| RT-3 | 还原复核 | 删除探针 | `npx vue-tsc --noEmit` | 退出码 0 |
| RT-4 | 便捷脚本 | 无 | `npm run type-check` | 等价 vue-tsc，退出码 0 |

## 2. RT-1 正向构建（实测记录）

命令：

```bash
cd apps/miniapp && npm run build:mp-weixin
```

实测输出（尾部）：

```text
> dance-miniapp@1.0.0 build:mp-weixin
> vue-tsc --noEmit && uni build -p mp-weixin

正在编译中...
DONE  Build complete.
运行方式：打开 微信开发者工具, 导入 dist/build/mp-weixin 运行。
```

- `vue-tsc --noEmit` 静默通过（无输出即 0 error），随后"正在编译中…"出现，证明 `&&` 左段成功后右段被执行。
- 产物核验：

```text
$ ls dist/build/mp-weixin/
api  app.js  app.json  App.wxml  app.wxss  common  components  pages ...
$ ls -la dist/build/mp-weixin/app.js
9 29 15:33 dist/build/mp-weixin/app.js
```

产物为当日（2026-09-29 15:33）新生成，mp-weixin 包结构完整（app.js / app.json / App.wxml / pages/ / components/ / api/）。

**结论：PASS。** 类型 0 error 时门禁不阻断正常出包。

## 3. RT-2 反向门禁（实测记录）

注入探针（仅用于验证，用后即删）：

```ts
// apps/miniapp/src/__type_gate_probe.ts
const probeValue: number = "this-is-not-a-number";
export { probeValue };
```

命令：

```bash
npm run build:mp-weixin > /tmp/f32-negative.log 2>&1; echo "EXIT_CODE=$?"
grep -c "正在编译中" /tmp/f32-negative.log
```

实测输出：

```text
EXIT_CODE=2
---LOG---
> dance-miniapp@1.0.0 build:mp-weixin
> vue-tsc --noEmit && uni build -p mp-weixin

src/__type_gate_probe.ts(2,7): error TS2322: Type 'string' is not assignable to type 'number'.
---UNI_BUILD_RUN_CHECK---
0
```

三个判定点全部成立：

1. vue-tsc 精确报出探针错误（TS2322，含文件/行列）；
2. 脚本整体退出码 **2**（非 0，CI 会判红灯）；
3. 日志中"正在编译中"出现次数 **0** —— `&&` 短路，`uni build` 未启动，dist 不会被失败包污染。

**结论：PASS。** 任意 TS 错误都会阻断 mp-weixin 构建，AC-4 满足。

## 4. RT-3 还原复核

删除探针文件后：

```bash
rm src/__type_gate_probe.ts
npx vue-tsc --noEmit; echo "VUE_TSC_EXIT=$?"
```

实测：

```text
VUE_TSC_EXIT=0
```

`git status` 无探针残留。**结论：PASS。**

## 5. RT-4 type-check 便捷脚本

`package.json` 新增 `"type-check": "vue-tsc --noEmit"`，与门禁左段同一命令；实测退出码 0。可供开发者编码期 / CI 分步骤调用，无需触发完整构建。

## 6. 关于 uni build 环境完整性的说明

本次 RT-1 在本机完整跑通 uni-app mp-weixin 编译并产出 `dist/build/mp-weixin/`，不存在"uni build 无法产出"的环境缺口；门禁的两段串联与退出码透传均为真实构建下的实测结论，非模拟。

## 7. 未覆盖项与原因

| 项 | 原因 |
|----|------|
| 微信开发者工具真机预览 / 真机 PATCH 联调 | 本 Feature 无运行时逻辑改动（仅类型 + 构建脚本）；PATCH 真机链路为既有实现既成事实，非本次变更面 |
| CI 平台（GitHub Actions / Jenkins 等）红灯验证 | 门禁以标准退出码表达成败（实测 0 / 2），任何执行 `npm run build:mp-weixin` 的 CI 均天然继承；CI yaml 是否已调用该脚本属接入项（见 review D-F3.2-2） |
| 小程序页面功能回归 | 无业务/UI 代码路径改动；类型层改动的等价性分析见 acceptance.md "行为等价性说明" |

## 8. 总结

| 用例 | 结果 |
|------|------|
| RT-1 正向（0 error → 出包成功） | PASS |
| RT-2 反向（有 error → 退出 2 + 短路） | PASS |
| RT-3 还原（0 error 恢复） | PASS |
| RT-4 type-check 脚本 | PASS |

门禁行为符合 AC-2 / AC-3 / AC-4，可进入验收。
