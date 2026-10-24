# F3.3 — Runtime Test Report

## 环境

- 后端：Python 3.12.13 / pytest 9.0.3 / pytest-asyncio / asyncpg
- 前端：Node.js / vue-tsc 2.2.0 / vite 5.2.8

## 后端测试

命令：
```bash
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_tenant_update.py -v
```

结果：**18 passed, 4 warnings in 4.35s**

| # | 测试 | AC | 结果 |
|---|------|----|------|
| 1 | test_admin_update_settings_success | AC-1 | PASS |
| 2 | test_settings_merge_semantics | AC-3 | PASS |
| 3 | test_invalid_cancel_minutes_zero | AC-5 | PASS |
| 4 | test_invalid_cancel_minutes_over_limit | AC-5 | PASS |
| 5 | test_invalid_advance_days_zero | AC-5 | PASS |
| 6 | test_invalid_string_value | AC-5 | PASS |
| 7 | test_super_admin_can_update_settings | AC-1 | PASS |
| 8 | test_super_admin_update_info_success | AC-2 | PASS |
| 9 | test_info_partial_update_preserves_other_fields | AC-4 | PASS |
| 10 | test_info_missing_name_returns_422 | AC-6 | PASS |
| 11 | test_admin_can_update_info | AC-2 | PASS |
| 12 | test_student_cannot_update_settings | AC-7 | PASS |
| 13 | test_student_cannot_update_info | AC-7 | PASS |
| 14 | test_unauthenticated_settings | AC-8 | PASS |
| 15 | test_unauthenticated_info | AC-8 | PASS |
| 16 | test_no_traceback_in_error_response | — | PASS |
| 17 | test_settings_trailing_slash_404 | AC-9 | PASS |
| 18 | test_info_trailing_slash_404 | AC-9 | PASS |

## 前端验证

| 验证 | 命令 | 结果 |
|------|------|------|
| 类型检查 | `npx vue-tsc --noEmit` | 0 error |
| 构建 | `pnpm run build` | ✓ built in 3.59s |

## 后端回归

test_rbac_enforcement.py 中 tenant/admin 相关测试：全部通过，无回归。

## 汇总判定

- 后端 18/18 PASS
- 前端 vue-tsc 0 error + build 成功
- 回归无影响

**结论：PASS，READY_FOR_ACCEPTANCE。**
