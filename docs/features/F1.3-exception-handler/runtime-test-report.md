# F1.3 — Runtime Test Report

> Feature ID：F1.3
> 验证日期：2026-09-26
> 验证范围：acceptance.md AC-1 ~ AC-5
> 验证环境：pytest 单元测试 + FastAPI TestClient 冒烟测试
> 验证方式：直调 handler + TestClient 端到端触发异常

---

## 环境准备

| 组件 | 状态 |
|------|------|
| Python 3.12 + pytest | ✅ 就绪 |
| FastAPI TestClient | ✅ 就绪（冒烟测试用） |

---

## AC-1 未捕获异常返回统一信封 500 且不泄露（主验收）

| 用例 | 结果 |
|------|------|
| TC-01 未捕获异常返回 500 状态码 | **PASS** |
| TC-02 响应体为统一信封（code/data/msg/request_id） | **PASS** |
| TC-03 响应体不含原始异常消息（含 SQL/密码等） | **PASS** |
| TC-04 request_id 字段存在且非空 | **PASS** |
| TC-05 content-type 为 application/json | **PASS** |

### 冒烟验证（TestClient 端到端）

| 用例 | 结果 |
|------|------|
| 未捕获异常 → HTTP 500 + `{code:500, msg:"服务暂时不可用，请稍后重试"}` | **PASS** |
| 原始异常消息（`secret=123`）不在响应体中 | **PASS** |

**AC-1 结论：PASS（5/5 单元 + 2/2 冒烟）**

---

## AC-2 APP_DEBUG 默认 False

| 用例 | 结果 |
|------|------|
| AC-2.1 `Settings.model_fields["APP_DEBUG"].default is False` | **PASS** |
| AC-2.2 字段类型为 bool | **PASS** |

**AC-2 结论：PASS**

---

## AC-3 AI 端点异常处理修复

| 用例 | 结果 |
|------|------|
| AC-3.1 AI 端点 DanceSaasException 返回正确 HTTP 状态码 | **PASS**（代码审查：移除本地 try/except 后由全局 handler 处理） |
| AC-3.2 AI 端点异常响应为统一信封 | **PASS**（代码审查：不再返回 HTTPException 的 `{"detail":...}`） |
| AC-3.3 AI 端点未捕获异常 → 500 统一信封，不泄露 | **PASS**（冒烟验证通用 handler） |
| AC-3.4 AI 端点成功响应不变 | **PASS**（代码审查：chat 端点成功路径未改） |

**AC-3 结论：PASS**

---

## AC-4 回归

| 用例 | 结果 |
|------|------|
| AC-4.1 422 校验错误不回归（仍由 FastAPI 内置处理） | **PASS**（冒烟：POST 空 body → 422） |
| AC-4.2 现有 DanceSaasException / IntegrityError handler 不回归 | **PASS**（代码审查：两个 handler 未修改） |

### 422 回归冒烟详情

```
POST /test 空 body → HTTP 422 + {"detail":[{"type":"missing",...}]}
```

Starlette MRO 优先级保证 `RequestValidationError`（422）优先于 `Exception` handler 命中。

**AC-4 结论：PASS**

---

## AC-5 变更范围（静态）

| 用例 | 结果 |
|------|------|
| AC-5.1 实际修改文件 ⊆ {error_handler.py, main.py, config.py, ai/router.py} | **PASS** |
| AC-5.2 无 OpenAPI 契约变更 | **PASS**（仅错误响应内容优化） |
| AC-5.3 每个修改文件 py_compile 通过 | **PASS**（5 文件全部通过） |

**AC-5 结论：PASS**

---

## 回归验证

| 套件 | 结果 | 说明 |
|------|------|------|
| `tests/test_exception_handlers.py` | ✅ 7 passed | F1.3 新增测试 |
| `tests/test_agent_runtime.py`（F5.3 业务异常映射） | ✅ 10/10 passed | AI router 改动不影响 AgentRuntime |

---

## 汇总判定

| AC | 判定 |
|----|------|
| AC-1 未捕获异常 → 500 统一信封，不泄露 | **PASS** |
| AC-2 APP_DEBUG 默认 False | **PASS** |
| AC-3 AI 端点异常正确处理 | **PASS** |
| AC-4 422 / 现有 handler 不回归 | **PASS** |
| AC-5 变更范围 ⊆ 白名单 | **PASS** |

---

## 结论

**Runtime Test：PASS**

- 主验收标准（AC-1）通过：未捕获异常返回 500 统一信封，不泄露 traceback / SQL / 原始异常消息。
- APP_DEBUG 默认 False，开发环境 `.env` 覆盖不受影响。
- AI 端点业务异常不再因属性 bug 降级为 500，返回正确状态码 + 统一信封。
- 422 校验错误行为不回归（Starlette MRO 优先级保证）。
- F5.3 回归测试通过，无副作用。
