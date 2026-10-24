# F1.5 — 用户流程

> Feature ID：F1.5
> 关联文档：[requirement.md](./requirement.md) / [acceptance.md](./acceptance.md)

## 1. 主流程：定时任务按租户循环处理

```
APScheduler 触发 scheduler 函数
  ↓
1. 查询所有 status=ACTIVE 的租户（tenants 表，不受租户过滤影响）
  ↓
2. 对每个 tenant 循环：
   ├─ set_tenant_id(tenant.id)        ← 设置 ContextVar，使 tenant_query 注入过滤
   ├─ try:
   │    async with SessionLocal() as db:
   │        执行业务逻辑（查询 / 更新本租户数据）
   │        db.commit()
   ├─ except Exception:
   │    logger.exception(...)          ← 记录单租户失败
   │    continue                       ← 不中断其他租户
   └─ finally:
        set_tenant_id(None)            ← 清理上下文
  ↓
3. 所有租户处理完毕，函数返回
```

### 修复前

```
APScheduler 触发 scheduler 函数
  ↓
async with SessionLocal() as db:
    执行业务逻辑（get_tenant_id() == None → 跳过租户过滤）
    ↓
    全表扫描所有租户数据 → 跨租户操作（BUG）
```

### 修复后

- 每个租户独立会话 + 独立上下文，`tenant_query` 自动注入 `WHERE tenant_id = :id`
- 只操作当前租户的数据

---

## 2. 异常隔离流程：单租户失败

```
租户列表 = [T1, T2, T3]
  ↓
T1: set_tenant_id(1) → 业务逻辑 → 成功 → set_tenant_id(None)
  ↓
T2: set_tenant_id(2) → 业务逻辑抛异常
     ├─ except: logger.exception("[租户2] 失败...")
     ├─ continue
     └─ finally: set_tenant_id(None)
  ↓
T3: set_tenant_id(3) → 业务逻辑 → 成功 → set_tenant_id(None)
  ↓
函数正常返回（T2 的失败不影响 T1/T3）
```

**关键点**：
- 异常被 `except Exception` 捕获，不向上传播
- `finally` 块保证 `set_tenant_id(None)` 一定执行，即使业务抛异常
- 循环继续处理下一个租户

---

## 3. 边界流程：无 ACTIVE 租户

```
APScheduler 触发 scheduler 函数
  ↓
查询 ACTIVE 租户 → 空列表
  ↓
直接 return（不调用 set_tenant_id，不打开任何业务会话）
```

---

## 4. 边界流程：租户内无待处理数据

```
租户 T1: set_tenant_id(1)
  ↓
async with SessionLocal() as db:
    查询待处理数据 → 空
    ↓
    continue（不 commit，不记成功日志）
  ↓
finally: set_tenant_id(None)
  ↓
处理下一租户
```

---

## 5. 涉及的 scheduler 函数与操作

| 函数 | 模块 | 业务操作 | 租户表 |
|------|------|---------|--------|
| `auto_finish_expired_schedules` | schedule | 过期排期 → FINISHED；预约状态流转 | course_schedules, bookings |
| `auto_cancel_underbooked_schedules` | schedule | 人数不足排期 → 取消（调 service） | course_schedules, courses, course_types |
| `auto_expire_membership_cards` | membership | 过期卡 → EXPIRED；次卡清零 | membership_cards, transactions |
| `auto_activate_membership_cards` | membership | 待激活卡 → ACTIVE；计算到期日 | membership_cards, products, transactions |
| `notify_expiring_membership_cards` | membership | 到期提醒日志 | membership_cards（只读） |
| `auto_unfreeze_membership_cards` | membership | 冻结到期 → 解冻 / 更新冲突原因 | membership_cards, freezes |

---

## 6. Permission / Authentication

- 定时任务不经过 HTTP 认证中间件，无用户身份。
- 租户隔离完全依赖 `set_tenant_id` + `tenant_query` ORM 事件注入。
- `operator_id=0`（系统自动操作）在 `cancel_schedule` 中标识系统操作，行为不变。

---

## 7. Error 态

| 场景 | 行为 |
|------|------|
| 查询租户列表失败 | 整个任务失败（无租户列表无法循环），异常向上传播由 APScheduler 记录 |
| 单租户业务异常 | `logger.exception` 记录，`continue` 处理下一租户 |
| 单租户 commit 失败 | 同上，异常被捕获，不影响其他租户 |
| 无 ACTIVE 租户 | 直接返回 |
