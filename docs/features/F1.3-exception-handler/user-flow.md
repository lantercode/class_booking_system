# F1.3 — 用户流程

> Feature ID：F1.3
> 关联文档：[requirement.md](./requirement.md) / [acceptance.md](./acceptance.md)

## 1. 主流程：正常 API 请求

```
用户发起请求 → Router → Service → Repository → DB
  ↓
返回统一信封 {code:0, msg:"success", data:{...}}
```

- 无异常时行为不变，响应结构与 F1.3 前完全一致。

---

## 2. 异常流程：未捕获异常（主修复目标）

```
用户发起请求 → Service 抛出未捕获异常（如 AttributeError）
  ↓
全局 unhandled_exception_handler 拦截
  ├─ 服务端：logger.exception 记录完整堆栈（含 path）
  └─ 客户端：HTTP 500 + 统一信封 {code:500, msg:"服务暂时不可用，请稍后重试", data:null, request_id}
```

### 修复前

- `debug=True`：返回完整 traceback（泄露内部路径、SQL、变量）
- `debug=False`：返回 `{"detail": "Internal Server Error"}`（非统一信封，前端解包失败）

### 修复后

- 始终返回统一信封 500，响应体不含任何技术细节
- 服务端日志保留完整堆栈供排查

---

## 3. 异常流程：业务异常（DanceSaasException）

```
用户发起请求 → Service 抛出 BusinessException / AuthException / ...
  ↓
全局 dance_saas_exception_handler 拦截
  └─ 返回 HTTP <code> + 统一信封 {code:<code>, msg:<业务消息>, data:null}
```

- 行为不变，F1.3 不修改此 handler。
- 示例：`AuthException("请先登录")` → HTTP 401 + `{code:401, msg:"请先登录"}`。

---

## 4. 异常流程：AI 端点

### 修复前

```
POST /api/v1/ai/chat → agent_runtime.chat 抛出 DanceSaasException
  ↓
ai/router.py 本地 except DanceSaasException:
  raise HTTPException(status_code=e.status_code, detail=e.message)
  ↓
AttributeError（e.status_code / e.message 不存在）
  ↓
被外层 except Exception 捕获 → HTTP 500 + {"code":50001, "message":"AI 服务暂时不可用"}
```

问题：业务异常（401/403/404）全部降级为 500，且返回非统一信封。

### 修复后

```
POST /api/v1/ai/chat → agent_runtime.chat 抛出异常
  ↓
（无本地 try/except）异常向上传播
  ├─ DanceSaasException → 全局 dance_saas_exception_handler → 正确状态码 + 统一信封
  └─ 其他 Exception → 全局 unhandled_exception_handler → 500 + 统一信封
```

---

## 5. 异常流程：请求校验错误（422）

```
用户发起请求 → Pydantic 校验失败（如缺必填字段）
  ↓
FastAPI 内置 RequestValidationError handler（MRO 优先于 Exception handler）
  ↓
HTTP 422 + FastAPI 默认格式 {"detail": [...]}
```

- 行为不变，F1.3 的通用 Exception handler 不覆盖 422（Starlette MRO 优先级保证）。

---

## 6. 配置流程：APP_DEBUG

### 开发环境

```
.env: APP_DEBUG=true
  ↓
config.py: APP_DEBUG = True（被 .env 覆盖）
  ↓
FastAPI debug=True + SQLAlchemy echo=True（开发便利）
```

### 生产环境

```
.env.prod: 未设置 APP_DEBUG（或 APP_DEBUG=false）
  ↓
config.py: APP_DEBUG = False（默认值）
  ↓
FastAPI debug=False + SQLAlchemy echo=False（安全）
  ↓
即使未捕获异常，也不返回 traceback（由通用 handler 兜底）
```

---

## 7. Error 态与空状态

| 场景 | 修复前响应 | 修复后响应 |
|------|-----------|-----------|
| 未捕获异常（debug=True） | traceback 泄露 | 500 统一信封 |
| 未捕获异常（debug=False） | `{"detail":"Internal Server Error"}` | 500 统一信封 |
| AI 端点业务异常 | 500 非统一信封（属性 bug） | 正确状态码 + 统一信封 |
| AI 端点未捕获异常 | `{"code":50001,"message":"..."}` | 500 统一信封 |
| 422 校验错误 | `{"detail":[...]}` | 不变 |

---

## 8. Permission / Authentication

- F1.3 不修改认证/授权逻辑。
- `AuthException`（401）、`PermissionException`（403）仍由 `dance_saas_exception_handler` 处理，返回正确状态码 + 统一信封。
- 未登录请求仍返回 401，行为不变。
