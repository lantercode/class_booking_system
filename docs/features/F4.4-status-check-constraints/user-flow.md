# F4.4 — 核心表 status 字段 Check 约束 · 用户流程

> Feature ID：F4.4 ｜ 日期：2026-10-02
> 本 Feature 为纯数据库结构变更，无终端用户可见交互；以下以"数据写入路径"视角描述流程。

---

## 1. 正常写入流程（约束放行）

```
Service（状态机校验，枚举赋值）
  → Repository（auto_commit=False，同事务）
  → SQLAlchemy flush/commit
  → PostgreSQL CHECK (status IN (...)) 校验通过
  → 落库成功
```

- 预约创建：`status = BookingStatus.BOOKED.value (1)` → 通过 `ck_bookings_status`。
- 预约取消/签到/完成/爽约：`status ∈ {2,3,4,5}` → 通过。
- 排期取消/完结：`status ∈ {2,3}` → 通过 `ck_course_schedules_status`。
- 会员卡激活/过期/冻结/作废：`status ∈ {1,2,3,6}`（发卡初值 `0`）→ 通过 `ck_membership_cards_status`。

## 2. 异常写入流程（约束拦截）

```
任意写入路径（含绕过 Service 的裸 SQL / 脚本 / 缺陷代码）
  → SQLAlchemy / 直接 SQL
  → PostgreSQL CHECK (status IN (...)) 校验失败
  → 抛 check_violation → SQLAlchemy IntegrityError
  → 事务回滚，非法行不落库
```

- `INSERT INTO bookings (status) VALUES (0/6/99)` → `IntegrityError`，0 行落库。
- `INSERT INTO course_schedules (status) VALUES (0/4/99)` → `IntegrityError`。
- `INSERT INTO membership_cards (status) VALUES (4/5/99)` → `IntegrityError`。
- `UPDATE ... SET status = <非法值>` 同样被拦截（Check 约束对 UPDATE 同样生效）。

## 3. migration 执行流程（运维视角）

```
alembic upgrade head
  → 同一事务内：
      1. 逐表统计越界 status 行数
         ├─ 全部 0 → 继续
         └─ 任一表 > 0 → raise RuntimeError（打印 表/status/行数 明细）
                         → 整批回滚，DB 维持原状，人工修正后重跑
      2. ADD CONSTRAINT ck_bookings_status / ck_course_schedules_status / ck_membership_cards_status
  → 提交，alembic_version = f44ab1c2d3e4

alembic downgrade -1
  → 反序 DROP 三个 Check 约束（不动数据）
  → alembic_version = f42cd3e4f5a6
```

## 4. 前端 / API 影响

- 无端点、无契约变化；前端 4 端（admin / student / teacher / miniapp）不感知。
- 非法状态写入若由业务缺陷触发，`IntegrityError` 经全局异常处理器返回统一信封 `{code, msg, data}`，不回显 SQL / traceback（contracts.md 约定不变）。
