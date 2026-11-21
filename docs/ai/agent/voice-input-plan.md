# AI 助手语音输入实施方案

> 目标：为小程序 AI 助手增加语音输入，容忍口音与口语化表达，且不削弱现有身份、权限与工具安全边界。
> 状态：方案设计（未修改代码）。ASR 选型已定：火山引擎语音识别。

## 1. 目标与非目标

### 目标

1. 学员可长按说话，松开后得到转写文本并**回填到输入框**，确认后发送。
2. 对带口音、废话多的语音，转写结果经过归一化后仍能被现有 AgentLoop 正确理解。
3. 识别置信度低时明确提示"没听清"，不把错字喂给模型。
4. 复用现有 `/api/v1/ai/chat` 与全部 Tool 安全机制，不新增业务写入路径。

### 非目标

- 不做实时流式对话（边说边出结果），本期只做「录音 → 转写 → 回填」。
- 不做说话人分离、情绪识别。
- 不修改业务 Service / Repository / 数据库结构。
- 不改变 `/ai/chat` 的请求与响应契约。
- 不做语音直接触发写操作（预约/取消仍只读拦截）。

## 2. 现状（基于真实代码）

| 位置 | 现状 |
|---|---|
| `apps/miniapp/src/components/AiChatPanel.vue` L103-L127 | 单个 `<input>` + 发送按钮，无录音入口 |
| `apps/miniapp/src/api/index.ts` L735-L753 | `aiChatApi` 仅 chat / getHistory / clearHistory |
| `apps/api/src/app/modules/ai/router.py` | 仅 `/chat`、`/history`、`/intents` |
| `ChatRequest.message` | `max_length=500` |
| `modules/upload/service.py` | 白名单仅图片/视频，绑定 Pillow 解码，**不复用** |
| `apps/api/src/app/ai/llm/` | 仅文本 Provider，无 ASR |
| `apps/api/src/app/middleware/rate_limiter.py` | 支持 `path_limits` / `user_key_paths`，可直接扩展 |

结论：语音链路是全新能力，前端、接口、Provider 三层都要新增，但**不触碰 AgentLoop 与 Tool**。

## 3. 总体架构

```
小程序录音(≤60s)
   │  multipart
   ▼
POST /api/v1/ai/transcribe   （JWT + 租户 + 限流）
   │
   ▼
AsrProvider（火山语音识别）
   │  { text, confidence }
   ▼
normalize_text()  纯规则清洗
   │
   ▼
返回前端 → 回填输入框（不自动发送）
   │  用户确认/编辑
   ▼
POST /api/v1/ai/chat  → AgentLoop → Tool → Service（完全复用）
```

### 关键决策

| 决策 | 方案 | 理由 |
|---|---|---|
| ASR 位置 | 后端代理 | 复用鉴权/租户/限流/审计；口音模型与热词可调 |
| 转写后行为 | **回填，不自动发送** | 口音必有误差，自动发送可能触发错误工具调用 |
| 音频留存 | 默认不落库 | 录音属敏感数据；只记元数据 |
| 归一化 | 纯规则函数 | 可单测、零成本；语义纠错交给 LLM |
| 长文本 | 超 500 字提示分段 | 不擅自放宽 `/chat` 上限 |

## 4. 接口契约

### POST /api/v1/ai/transcribe

请求：`multipart/form-data`

| 字段 | 类型 | 约束 |
|---|---|---|
| `file` | UploadFile | mp3 / m4a / aac / wav / amr；≤ 5MB；时长 ≤ 60s |
| `session_id` | str | 同 `/chat`：`^[A-Za-z0-9_-]{1,64}$` |

响应（沿用统一信封）：

```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "text": "我这周还剩多少次课",
    "raw_text": "嗯…那个我这周还剩多少次课啊",
    "confidence": 0.86,
    "duration_ms": 3200,
    "provider": "volc",
    "truncated": false
  }
}
```

错误约定：

| 场景 | HTTP | 提示 |
|---|---|---|
| 未登录 | 401 | 请先登录 |
| 格式/大小/时长不合法 | 400 | 语音格式不支持 / 录音过长 |
| 静音或无人声 | 400 | 没有听到声音，请重试 |
| 置信度低于阈值 | 200 + `text` 为空 | 没听清，请再说一遍 |
| ASR 超时/上游错误 | 502 | 语音识别失败，请重试 |
| 超过用户限流 | 429 | 操作太频繁 |

说明：低置信度返回 200 而非 4xx，因为这是「识别结果不可用」而非「请求错误」，前端只需提示重录。

## 5. 配置项（core/config.py 新增）

| 变量 | 默认 | 说明 |
|---|---|---|
| `AI_ASR_ENABLED` | `false` | 总开关，关闭时接口返回 404/403，前端隐藏按钮 |
| `AI_ASR_PROVIDER` | `volc` | Provider 名 |
| `AI_ASR_APP_ID` | 空 | 火山语音应用 ID |
| `AI_ASR_ACCESS_TOKEN` | 空 | 访问令牌，`repr=False`，禁止入日志 |
| `AI_ASR_CLUSTER` | 待确认 | 火山识别集群/模型标识 |
| `AI_ASR_BASE_URL` | 待确认 | 识别服务地址 |
| `AI_ASR_TIMEOUT_MS` | `8000` | 单次识别超时 |
| `AI_ASR_MAX_SECONDS` | `60` | 音频时长上限 |
| `AI_ASR_MAX_BYTES` | `5242880` | 5MB |
| `AI_ASR_MIN_CONFIDENCE` | `0.70` | 低于则提示重录 |
| `AI_ASR_HOTWORDS` | 见 §7 | 热词表（逗号分隔） |
| `AI_ASR_ENABLED_TENANTS` | 空 | 灰度租户白名单，语义同 `AI_LLM_ENABLED_TENANTS` |
| `AI_ASR_RATE_LIMIT` / `WINDOW` | `10` / `60` | 用户级限流（比 chat 更严） |

校验规则（与 LLM 配置同风格，仅启用时校验）：

- 启用时 `AI_ASR_APP_ID` / `AI_ASR_ACCESS_TOKEN` 必填；
- `AI_ASR_TIMEOUT_MS` 必须小于前端等待上限；
- `AI_ASR_MAX_SECONDS * 16000` 与 `AI_ASR_MAX_BYTES` 保持合理关系（避免"能传不能识别"）。

## 6. 文件改动清单

### 后端新增

| 文件 | 职责 |
|---|---|
| `ai/asr/__init__.py` | 导出 Provider 与工厂 |
| `ai/asr/base.py` | `AsrProvider` 协议、`AsrResult`、异常体系（`AsrTimeoutError` / `AsrUpstreamError` / `AsrInvalidAudioError`） |
| `ai/asr/volc.py` | 火山语音识别实现：请求构造、鉴权头、状态码映射、超时与有限重试（仅网络/5xx，不重试参数错误） |
| `ai/asr/factory.py` | 单例 + `is_asr_enabled_for_tenant()` |
| `ai/asr/audio.py` | 服务端音频校验：MIME/扩展名/大小/时长/静音检测（不依赖前端声明） |
| `ai/text/__init__.py`、`ai/text/normalize.py` | 口语归一化纯函数 |

### 后端修改

| 文件 | 改动 |
|---|---|
| `modules/ai/router.py` | 新增 `POST /transcribe`：`get_current_user` + 租户上下文 + 读取文件 + 调用 service 流程 + 统一信封 |
| `core/config.py` | §5 配置项 + 校验 |
| `main.py` | 限流 `path_limits` 增加 `/api/v1/ai/transcribe`，`user_key_paths` 包含该路径 |
| `ai/agent/prompts.py` | 增加语音输入容错与追问规则（§8） |
| `.env.example` / `.env.prod.example` / `infra/docker/docker-compose.prod.yml` | 同步新增变量（沿用 `sync-env.sh` 流程） |

### 前端修改

| 文件 | 改动 |
|---|---|
| `components/AiChatPanel.vue` | 麦克风按钮、长按录音、时长提示、上传态、回填输入框、失败 Toast、能力降级 |
| `api/index.ts` | `aiChatApi.transcribe(filePath, sessionId)`，复用 `uploadFile` 封装 |

### 明确不改

`ai/agent/loop.py`、`ai/agent/runtime.py`、`ai/mcp_server.py`、`ai/llm/*`、所有 `modules/*/service.py`、`repository.py`、`models.py`、`alembic/`。

## 7. 口音与废话处理

### 7.1 热词表（ASR 层）

初始热词（按业务真实词汇）：

```
中国舞片段, 常规课, 特色课, 私教课, 次卡, 年卡, 月卡, 课时,
预约, 取消预约, 排期, 签到, 张老师, 李老师
```

实现要点：

- 热词从配置读取，**不硬编码在代码里**，便于运营调整；
- 老师姓名属于租户数据，理想做法是运行时按租户查询后拼接（第二阶段）；第一阶段先用配置里的通用词 + 课程类型词；
- 热词数量受上游限制，超出需截断并记录日志。

### 7.2 归一化规则（文本层）

| 规则 | 示例 |
|---|---|
| 删除句首/句中语气词 | 「嗯…那个我想问」→「我想问」 |
| 删除填充词 | 就是、然后、这个、那个（连续出现时） |
| 合并重复字词 | 「我我我想」→「我想」 |
| 去首尾空白、全角转半角 | — |
| 句末无标点时补「？」 | 疑问句补问号 |
| 超长截断 | 超过 500 字截断并置 `truncated=true` |
| 不做的 | 不改数字、不纠错错别字、不做同义改写（交给 LLM） |

### 7.3 置信度策略

| 置信度 | 行为 |
|---|---|
| ≥ 0.70 | 正常回填 |
| 0.55 ~ 0.70 | 回填 + 前端提示「识别可能不准，请检查后发送」 |
| < 0.55 | 不回填，提示「没听清，请再说一遍」 |
| 上游未返回置信度 | 视为通过，但记录 `confidence=null` 便于后续评估 |

**UNKNOWN（需在接入火山接口时确认）**：火山一句话识别/流式识别的响应中，置信度字段名与取值范围（0–1 还是 0–100、是句级还是字级）必须按实际文档核对，不能凭经验写死。确认方式：拿到测试账号后用一段已知音频调用一次，打印完整响应结构。

### 7.4 Prompt 层

在 `prompts.py` 增加：

```
用户可能通过语音输入，文本带有口语化表达、语气词或轻微识别错误。
请优先理解其真实意图；当关键信息（课程、日期、卡种）缺失或矛盾时，
最多追问一次，不要自行编造参数。
```

不增加额外的模型调用轮次。

## 8. 安全、合规与限流

| 项 | 要求 |
|---|---|
| 认证 | 必须 `get_current_user`；未登录直接 401 |
| 租户 | 取 ContextVar，**不接受前端传 tenant_id**；音频校验与 ASR 调用都在租户上下文内 |
| 文件校验 | 服务端校验 MIME + 扩展名 + 大小 + 时长 + 静音；不信任前端 `content_type` |
| 音频留存 | 默认不写入 OSS/磁盘，处理完即释放 |
| 日志 | 只记 `duration_ms`、`confidence`、`text_length`、`tenant_id`、`user_id`；**不记转写全文**，不记音频内容 |
| 注入 | 转写文本与用户输入同等对待，复用现有 Prompt 注入防护 |
| 限流 | 用户级 10 次/分钟（比 chat 的 20 次更严，ASR 成本更高） |
| 出网 | 服务器需放行火山语音识别域名（与方舟同样的白名单工作） |

## 9. 成本控制

- 单次 ≤ 60 秒，超出由前端停止录音、服务端二次校验。
- 用户级限流 + 可选日配额（`AI_ASR_DAILY_QUOTA`，第一阶段可不做）。
- 失败不自动重试超过 1 次，避免异常放大成本。
- 只对转写文本走 `/chat`，不因语音额外增加模型调用。

## 10. 测试与验收

### 单元测试

| 用例 | 断言 |
|---|---|
| `normalize_text` 去语气词 | 输入含「嗯/那个/就是」，输出不含 |
| 重复字合并 | 「我我我想」→「我想」 |
| 超长截断 | 501 字 → 500 字且 `truncated=true` |
| 大小/时长/格式校验 | 越界返回 400，不调用 Provider |
| 置信度分档 | 三档行为符合 §7.3 |
| Provider 错误映射 | 超时→`AsrTimeoutError`，5xx→`AsrUpstreamError`，不泄露上游原文 |
| 开关关闭 | 接口返回不可用，不初始化 Provider |

### 集成测试

- 上传合法音频 → mock ASR → 返回文本（不联网）；
- 跨租户/未登录取音频 → 401/403；
- 限流：11 次/分钟触发 429；
- 转写后调用 `/chat` 全链路（ASR mock + LLM mock）。

### 真实场景验收

| 项 | 方法 |
|---|---|
| 口音 | 3–5 位真实用户各录 20 条（含方言口音） |
| 废话多 | 刻意加「嗯、那个、就是」的 10 条 |
| 专业术语 | 「中国舞片段」「次卡」「私教课」各 5 条 |
| 噪声/静音 | 静音、环境噪音各 5 条，验证提示文案 |

指标：转写准确率（人工标注）、意图命中率、追问率、ASR P95 延迟、单次成本。

### 验收红线

1. 低置信度**必须提示**，不得静默回填错文本；
2. 转写结果**不自动发送**；
3. 语音链路不得新增任何写操作能力；
4. `AI_ASR_ENABLED=false` 时，功能与现在完全一致（按钮隐藏、接口不可用）。

## 11. 分阶段实施

| 阶段 | 内容 | 交付物 |
|---|---|---|
| A | 后端 `/transcribe`（Provider 用 mock）+ 配置项 + 音频校验 + 单测 | 可上传、可返回假文本 |
| B | 前端录音上传 + 回填 + 失败降级 | 小程序可长按说话 |
| C | 接真实火山 ASR + 热词表 + 置信度分档 | 真实可用 |
| D | `normalize_text` + prompt 容错 + 灰度（单租户） | 可选上线 |

每阶段独立可回滚：`AI_ASR_ENABLED=false` 即完全关闭。

## 12. 风险与 UNKNOWN

| 类型 | 内容 | 处理 |
|---|---|---|
| UNKNOWN | 火山接口路径、鉴权方式（APP ID + Token 还是 AK/SK）、置信度字段 | 接入前用测试账号跑通一次并记录响应样例 |
| UNKNOWN | 是否支持热词、热词数量上限 | 同上门槛验证 |
| 风险 | 方言识别率低 | 依赖「回填可编辑 + 置信度提示」兜底，不作为自动流程 |
| 风险 | 服务器出网未放行 | 部署前 `nc -vz` 验证，否则接口 502 |
| 风险 | 录音隐私合规 | 默认不留存；需在隐私政策中声明麦克风用途 |
| 风险 | 小程序审核 | `app.json` 声明 `scope.record` 用途说明 |
| 风险 | 长语音被截断导致语义缺失 | 前端 60s 硬停 + 提示分段录制 |

## 13. 与面试题目的对应

| 面试主题 | 本方案可讲的点 |
|---|---|
| Function Calling 安全 | 语音只是输入方式，工具白名单/参数校验/身份链不变 |
| 幂等与并发 | 转写接口天然只读，不存在重复扣次；限流防刷 |
| Context Engineering | 语音文本更啰嗦，靠归一化 + Token 预算控制上下文 |
| 可观测性 | 新增 `asr_trace`（时长、置信度、耗时、是否低于阈值） |
| 多租户隔离 | 音频处理全程在租户上下文，热词按租户可扩展 |
