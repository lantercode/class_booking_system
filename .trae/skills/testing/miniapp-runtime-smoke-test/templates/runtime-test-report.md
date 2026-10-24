# <FEATURE-ID> — Runtime Smoke Test Report

> Feature：<ID + 名称>
> 日期：<YYYY-MM-DD>
> 验证人/工具：<browser_use / 人工 / curl>
> 环境：<H5 localhost:5173 ｜ 微信开发者工具 + 版本号>
> 后端：<http://127.0.0.1:8000 ，租户 slug：xxx，账号：脱敏手机号>

## 环境准备记录

| 组件 | 状态 | 说明 |
|------|------|------|
| Docker PG/Redis | | |
| 后端 API | | |
| H5 / 开发者工具 | | |
| 测试账号 | | |

**环境限制声明**：<H5 无法覆盖、需转微信开发者工具的项；无则写"无">

## 用例记录（每条必须含全部字段）

### TC-<编号>：<名称> — <PASS|FAIL|BLOCKED|UNKNOWN|NOT TESTED>

- **Preconditions**：
- **Steps**：
- **Expected**：
- **Actual**：
- **Evidence**：<截图路径 / 控制台输出 / curl 命令与状态码>
- **Verified By**：
- **Environment**：
- **Timestamp**：

## 横切场景清单（按需增删）

- [ ] 页面加载无 ReferenceError / 白屏红屏
- [ ] onMounted 链路完整
- [ ] Loading / 空态 / Error toast
- [ ] 未登录拦截（toast + 回跳，不崩）
- [ ] 无效/过期 token（API 401 + 前端拦截）
- [ ] 角色不匹配
- [ ] 配置/网络失败降级
- [ ] 异步返回前组件销毁
- [ ] 控制台无未捕获异常

## 汇总

| 用例组 | PASS | FAIL | BLOCKED | UNKNOWN | NOT TESTED |
|--------|------|------|---------|---------|------------|
| AC-x | | | | | |
| **合计** | | | | | |

**最终判定**：PASS（0 FAIL 且限制项有替代路径）/ FAIL / BLOCKED

## UNKNOWN 与下一步

| 项 | 原因 | 微信开发者工具复现步骤 |
|---|------|----------------------|

## 新发现缺陷 / 技术债

<只记录，不在本 Skill 修复；编号交回 Feature 生命周期登记>
