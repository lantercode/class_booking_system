# F1.3 — Static Verification

> 阶段：STATIC VERIFICATION
> 日期：2026-09-26

## 1. 范围守卫（minimal-change-guard）

### 1.1 白名单

```
apps/api/src/app/middleware/error_handler.py
apps/api/src/app/main.py
apps/api/src/app/core/config.py
apps/api/src/app/modules/ai/router.py
apps/api/tests/test_exception_handlers.py（新建）
```

### 1.2 范围复核结论

- ✅ 4 个修改文件 + 1 个新建测试文件均在 `git status` 中
- ✅ 白名单外，F1.3 相关目录无其他文件被修改
- ✅ `git diff --check` 对 5 个文件 → 无空白错误

### 1.3 逐文件 diff 审查

- **error_handler.py**：仅新增 `unhandled_exception_handler` 函数，现有两个 handler 未改
- **main.py**：仅新增 import + 1 行 `add_exception_handler`，其余未动
- **config.py**：仅 L35 `APP_DEBUG` 默认值 `True` → `False`
- **ai/router.py**：移除 3 个端点的 try/except 块 + 清理未使用 import；计时逻辑保留
- **test_exception_handlers.py**：新建，仅测试代码

## 2. 编译验证

| 文件 | py_compile |
|------|-----------|
| `middleware/error_handler.py` | ✅ OK |
| `main.py` | ✅ OK |
| `core/config.py` | ✅ OK |
| `modules/ai/router.py` | ✅ OK |
| `tests/test_exception_handlers.py` | ✅ OK |

## 3. 契约验证（AC-5.2）

- 无新端点、无删除端点
- 请求/响应 DTO 未变
- 仅错误响应内容优化（500 响应体从 `{"detail":...}` 变为统一信封），不影响 OpenAPI schema

## 4. 异常处理优先级验证

通过 Starlette MRO 机制确认（冒烟测试证实）：

| 异常类型 | 命中 handler | HTTP 状态 |
|---------|-------------|----------|
| `RequestValidationError`（422） | FastAPI 内置 | 422（不回归） |
| `DanceSaasException` 子类 | `dance_saas_exception_handler` | code 值 |
| `IntegrityError` | `integrity_error_handler` | 409 |
| 其他 `Exception` | `unhandled_exception_handler` | 500 |

## 5. 静态结论

| AC | 判定 |
|----|------|
| AC-5.1 变更范围 ⊆ 白名单 | ✅ PASS |
| AC-5.2 无契约变更 | ✅ PASS |
| AC-5.3 py_compile | ✅ PASS |
