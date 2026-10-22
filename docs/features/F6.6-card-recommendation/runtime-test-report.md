# F6.6 运行时测试报告

> 环境：macOS，本地 PostgreSQL 15 + Redis，`apps/api/.venv`（Python 3.12）。
> 日期：2026-10-22。结果词：PASS / FAIL / BLOCKED / NOT TESTED。

## 1. 新增测试

命令：

```bash
cd apps/api
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_card_recommendation.py tests/integration/test_card_recommendation.py -q
```

结果：**27 passed**（unit 18 + integration 9）。

| AC | 用例 | 结果 |
|----|------|------|
| B-1 | `test_b1_expire_at_ascending` | PASS |
| B-2 | `test_b2_null_expire_at_last` | PASS |
| B-3 | `test_b3_remaining_credits_ascending_within_same_expire` | PASS |
| B-4 | `test_b4_created_at_then_id_breaks_ties` | PASS |
| B-5 | `test_b5_count_card_before_no_remaining_card_on_same_expire` | PASS |
| B-6 | `test_b6_*`（状态/未生效/过期/课程/用尽） | PASS |
| B-7 | `test_b7_pending_period_card_without_valid_from_is_available` | PASS |
| B-8 | `test_b8_pending_period_card_with_valid_from_is_unavailable` | PASS |
| B-9 | `test_b9_expire_at_same_day_available_next_day_unavailable` | PASS |
| B-10 | `test_b10_*`（无卡/聚合/有可用） | PASS |
| D-7 | `test_d7_unknown_card_type_is_excluded_even_when_active` | PASS |
| A-5 复核 | `test_is_bookable_card_delegates_shared_reason` | PASS |
| C-1/C-2 | `test_c1_c2_sorted_recommendation_is_stable` | PASS |
| C-3 | `test_c3_exclusion_rules_end_to_end` | PASS |
| C-4 | `test_c4_all_cards_excluded_returns_reason_message` | PASS |
| C-5 | `test_c5_student_without_cards` | PASS |
| C-6 | `test_c6_unauthenticated_returns_401` | PASS |
| C-7 | `test_c7_missing_schedule_returns_404` | PASS |
| C-8 | `test_c8_cross_tenant_schedule_returns_404` | PASS |
| C-9 | `test_c9_recommend_is_read_only` | PASS |
| E-2 | `test_e2_other_students_cards_not_returned` | PASS |
| E-4 | C-7 / C-8 断言响应不含 traceback/SQL/内部地址 | PASS（404/401 路径） |

## 2. 回归

命令：

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/unit/test_membership_card_state_machine.py \
  tests/integration/test_membership_period_card_lifecycle.py \
  tests/integration/test_period_card_booking_validation.py \
  tests/integration/test_booking_card_authorization.py -q
```

结果：**29 passed**。

说明：`is_bookable_card` 由共享函数委托后，状态机与期卡生命周期用例全部保持通过，未发现行为漂移。

## 3. 构建与类型

| 项 | 命令 | 结果 |
|----|------|------|
| 小程序类型 | `cd apps/miniapp && pnpm type-check` | PASS |
| 小程序构建 | `pnpm build:mp-weixin` | PASS（DONE Build complete） |
| OpenAPI | `pnpm gen:types` | PASS（81 路径） |

## 4. 未覆盖 / UNKNOWN

| 项 | 原因 | 替代验证 |
|----|------|---------|
| E-4 的 500 分支 | 未构造确定性 500 触发点 | 已验证 401/404 不泄露；全局 handler 由既有 F1.3 覆盖 |
| 真机选卡与空态 | 需要微信开发者工具/真机 | 列入 Stage 11 人工验收 |
| 与 `create_booking` 的端到端一致性 | 推荐为只读，不写库 | 人工抽查：推荐卡可下单、排除卡被拒 |

## 5. 结论

**TESTING PASS**（0 FAIL，2 项 UNKNOWN 已有替代验证路径）。
