# P2｜语音输入落地计划

> 设计依据：[voice-input-plan.md](../agent/voice-input-plan.md)（架构、契约、安全、成本）。
> 本文件只写执行步骤、文件改动与验收。

## 前置确认（阻塞项）

| # | 待确认 | 确认方式 |
|---|---|---|
| 1 | 火山语音识别的接口路径与鉴权方式（APP ID + Token 还是 AK/SK） | 控制台文档 + 测试账号跑通一次 |
| 2 | 响应中置信度字段名与取值范围 | 调用一次后打印完整响应结构 |
| 3 | 是否支持热词及数量上限 | 同上 |
| 4 | 服务器出网是否放行识别域名 | `docker exec dance-api python -c "import socket; socket.create_connection((host,443),5)"` |

**这四项未完成前不进入阶段 C。**

## 阶段 A：后端骨架（ASR 先用 mock）

| # | 任务 | 文件 | 验收 |
|---|---|---|---|
| A1 | 新增配置项与校验（`AI_ASR_*`，默认关闭） | `core/config.py` | 关闭时不因缺 Token 启动失败；启用时缺 Token 直接报错 |
| A2 | Provider 协议、结果 DTO、异常体系 | `ai/asr/base.py`（新增） | 单测覆盖异常映射 |
| A3 | Mock Provider（返回固定文本与置信度） | `ai/asr/factory.py` | 测试用 |
| A4 | 服务端音频校验：MIME/扩展名/大小/时长/静音 | `ai/asr/audio.py`（新增） | 越界返回 400，不调用 Provider |
| A5 | 接口 `POST /api/v1/ai/transcribe` | `modules/ai/router.py` | 登录态 + 租户；multipart 上传 |
| A6 | 限流：用户级 10 次/分钟 | `main.py` | 第 11 次返回 429 |
| A7 | 单测：校验、限流、开关关闭 | `tests/unit/test_ai_asr_*.py` | 全绿 |

**阶段 A 完成标准**：`AI_ASR_PROVIDER=mock` 时可上传音频并拿到假文本，`AI_ASR_ENABLED=false` 时接口不可用。

## 阶段 B：前端录音

| # | 任务 | 文件 | 验收 |
|---|---|---|---|
| B1 | 麦克风按钮（长按录音、松手结束、60s 自动停） | `components/AiChatPanel.vue` | 真机可录音并显示时长 |
| B2 | 录音权限申请与拒绝引导 | 同上 | 拒绝后弹引导，不崩溃 |
| B3 | 上传接口封装 | `api/index.ts`（`aiChatApi.transcribe`） | 走现有 request，自动带 JWT/租户头 |
| B4 | 转写结果回填输入框（**不自动发送**） | `AiChatPanel.vue` | 用户可编辑后手动发送 |
| B5 | 失败态：Toast + 保留键盘输入 | 同上 | 断网/超时均有提示 |
| B6 | 能力降级：不支持录音的平台隐藏按钮 | 同上 | H5 不支持时纯文本可用 |

**阶段 B 完成标准**：小程序可「说话 → 看到文字 → 编辑 → 发送」，全程不自动触发工具调用。

## 阶段 C：真实 ASR 接入

| # | 任务 | 文件 | 验收 |
|---|---|---|---|
| C1 | 火山 Provider 实现（超时、错误映射、有限重试） | `ai/asr/volc.py`（新增） | 超时→`AsrTimeoutError`，5xx→`AsrUpstreamError` |
| C2 | 置信度分档：≥0.70 回填；0.55–0.70 回填+提示；<0.55 提示重录 | `router.py` / 前端 | 三档行为符合设计 |
| C3 | 热词表（配置读取，不硬编码） | `core/config.py` | 修改配置后识别生效 |
| C4 | 静音/无人声检测 | `ai/asr/audio.py` | 返回「没有听到声音」 |
| C5 | 集成测试（mock 上游） | `tests/integration/` | 全链路不联网 |

**阶段 C 完成标准**：真实口音样本转写可用，低置信度有提示。

## 阶段 D：归一化与灰度

| # | 任务 | 文件 | 验收 |
|---|---|---|---|
| D1 | `normalize_text`：去语气词、合并重复、补标点、超长截断 | `ai/text/normalize.py`（新增） | 单测覆盖规则表 |
| D2 | Prompt 增加语音容错与「最多追问一次」 | `ai/agent/prompts.py` | 反问一次后给出结果 |
| D3 | 灰度：`AI_ASR_ENABLED_TENANTS` | `core/config.py` | 未在名单内租户接口不可用 |
| D4 | 指标：时长、置信度、耗时、低于阈值次数 | 日志 | 可用 `grep` 统计 |

## 验收清单

| 层 | 标准 |
|---|---|
| 单测 | 校验/阈值/归一化/Provider 错误映射全绿 |
| 集成 | 上传→转写→chat 全链路（双 mock） |
| 真机 | 3–5 位真实用户各 20 条（含口音、废话、术语、静音） |
| 安全 | 未登录 401、跨租户 403、音频不落盘、日志不含转写全文 |
| 回滚 | `AI_ASR_ENABLED=false` + 重启即恢复纯文本 |

## 风险

| 风险 | 应对 |
|---|---|
| 方言识别率低 | 回填可编辑 + 低置信度提示，不做自动发送 |
| 小程序麦克风权限审核 | 提前在 `app.json` 声明用途 |
| ASR 成本超预期 | 用户级限流 + 60s 上限 |
| 与 P3 推送冲突 | 语音只走 HTTP，不占用长连接 |
