---
name: minimal-change-guard
description: 保护外科手术式修改的变更范围，修改前后用 git 检查把实际变更文件与显式 expected-files 白名单核对，并按语言执行最小静态验证。用于 bugfix、审计整改、最小补丁的实施与验收。不用于大范围 Feature 分支。
---

# Minimal Change Guard

保证一次"最小修改"真的最小：**实际修改文件 ⊆ expected scope**，且每个文件只含预期改动。可独立使用，也是 feature-delivery-lifecycle 的阶段 7/8 强制环节。

首个完整样板：`docs/features/F3.1-miniapp-crash-fix/static-verification.md`（含"预存改动混入 diff"的真实处置案例）。

## When to Use

- P0/P1 bugfix、审计报告整改、单文件/少量文件的精确修复
- 用户明确要求"只改 X""不顺手修别的""最小改动"
- Feature 验收时核对 diff 范围

**Do Not Use**：正常 Feature 开发分支（多文件协同变更用生命周期 Skill 的 STATIC 门控即可，判定逻辑相同）。

## 修改前（冻结基线）

1. `git status --short` —— 识别**所有**已存在的工作区改动与未跟踪文件
2. 对目标文件确认：若已被改过，必须向用户确认预存改动归属，禁止覆盖
3. 与用户/需求冻结 **expected files 白名单**与每个文件的**预期改动性质**（如"仅 +1 行 import"）
4. 记录环境基线：静态检查当前错误数（如 vue-tsc 错误计数），作为"不增加"的对比基准

禁止：覆盖用户已有修改、自动清理无关工作区改动、任何 destructive git 操作。

## 修改后（逐项执行，缺一不可）

```bash
git diff --name-only      # 实际变更文件清单
git diff --stat           # 文件级增删行数
git diff --check          # 空白符/冲突标记
git diff --numstat        # 精确增删行数
git diff -- <每个目标文件>  # 逐文件审读全部 +/- 行
```

可直接用 `scripts/verify-scope.sh <expected-file>...` 完成白名单比对与 diff 检查（脚本退出码即判定）。

### 逐文件核对内容

- [ ] 实际文件清单 ⊆ expected files（未跟踪新文件也要查：`git ls-files --others --exclude-standard`）
- [ ] 每个文件的 +/- 行与"预期改动性质"一致
- [ ] 无业务逻辑变更、无无关格式化、无自动修复外溢、无 import 排序/引号风格等顺手改动
- [ ] 预存改动与本次改动可区分（必要时用 `git show HEAD:<file>` 比对归属）
- [ ] 错误数对比：静态检查结果不劣于基线

### 按语言执行最小静态验证（以真实 package.json / pyproject 为准，先读再跑，不假设脚本名）

| 改动位置 | 最小验证 |
|---------|---------|
| `apps/api/**/*.py` | 每文件 `python3 -m py_compile <file>`；按风险跑 pytest 对应层级（见 `.trae/rules/testing/`） |
| `apps/miniapp/` | 无 lint/typecheck 脚本时用 `npx vue-tsc --noEmit` 计数对比 + `npm run build:mp-weixin` |
| Web 三端 / packages | 读取该包 package.json 后执行其真实 `build`/`type-check` 脚本 |

## 判定

- **PASS**：实际修改文件 ⊆ expected scope；每个文件仅有预期改动；静态验证不劣于基线
- **FAIL**：出现白名单外文件、意外业务改动、格式化外溢、静态检查劣化
  - FAIL 时**不修改代码**，只报告问题文件/行与处置选项（拆分提交、用户确认归属、还原后重验）
- 预存的他人改动混入 diff：本次改动本身可判 PASS，但必须显式标注并给出提交粒度建议，不得静默

## 输出

写入 Feature 的 `static-verification.md`（独立使用时直接向用户报告）：执行命令与结果、逐文件核对表、AC 映射的 PASS/FAIL、FAIL 问题清单、UNKNOWN。

## 边界

- 只做核对与报告；不替用户做提交、还原、stash 决策
- 不复制 `.trae/rules/` 中的语言/架构约束
