# F4.5 — 排期创建并发安全 · 用户流程

> Feature ID：F4.5 ｜ 日期：2026-10-02
> 入口：管理端 / 教师端创建排期 `POST /api/v1/schedules`（HTTP 契约不变），经 `ScheduleService.create_schedule`。

---

## 1. 主流程：单次合法创建（无并发冲突）

```
Router（Depends(get_current_user) + @require_permissions("schedule:create")）
  → Service.create_schedule
      ① 纯校验（重试外）：end>start、预约开放/截止、取消截止、教室存在且 status=1
      ② 进入尝试循环（最多 3 次）：
           rollback()                        # 关闭上游(认证/RBAC)只读事务
           connection(execution_options={"isolation_level":"SERIALIZABLE"})
           find_conflicts(use_lock=False)    # 同事务快照谓词读（禁用 SKIP LOCKED，见 §2.1）
             ├─ 有冲突 → rollback + BusinessException(400)（见异常流程）
             └─ 无冲突 → repo.create(auto_commit=False) → commit → refresh
      ③ 返回 ScheduleResponse（统一信封 data）
```

- 与改造前对用户的差异：成功路径响应体、状态码完全不变；仅底层事务隔离级别提升。

## 2. 并发流程：两个请求创建时间重叠排期（AC-1）

```
事务 A（教师 T，10:00~11:00）               事务 B（教师 T，10:00~11:00）
  BEGIN ISOLATION LEVEL SERIALIZABLE          BEGIN ISOLATION LEVEL SERIALIZABLE
  SELECT ... <时间谓词>（快照读）→ 空           SELECT ... <时间谓词>（快照读）→ 空
  INSERT 排期 A                                （快照中仍无 A）
  COMMIT ✅                                    INSERT 排期 B
  （A 先提交，获得谓词锁 rw-依赖）               COMMIT → PostgreSQL SSI 检测危险结构
                                                   → SerializationError 40001
                                              Service 捕获 40001：
                                                · 若重试时 A 已可见 → 冲突检查非空
                                                  → BusinessException(400)「该教师时间冲突…」
                                                · 若再次 40001 且未耗尽 → 继续重试
                                                  耗尽 → BusinessException(500) 友好提示
最终：DB 恰好 1 行；一个成功、一个收到明确业务错误
```

> 冲突检查为**普通快照谓词读**（`use_lock=False`），不带 `FOR UPDATE / SKIP LOCKED`：空集双插由 SSI 谓词锁兜底（上图），已存在冲突行由快照读直接可见（§2.1）。

### 2.1 并发流程：冲突行已存在但正被预约/取消事务持锁（AC-5b，评审回归）

```
事务 X（预约/取消，READ COMMITTED）         事务 C（创建排期，SERIALIZABLE）
  已存在 NORMAL 排期 S（教师 T，10:00~11:00，已提交）
  SELECT ... WHERE id=S FOR UPDATE             BEGIN ISOLATION LEVEL SERIALIZABLE
  （扣/回补 booked_count，事务未提交，           SELECT ... <时间谓词>（快照读）
   持续持有 S 的行锁）                             → S 在快照中可见（不受 X 行锁影响）
                                                 → has_conflict=True
                                                 rollback + BusinessException(400)
                                                  「该教师时间冲突…」
最终：拒绝创建，DB 仍仅 S 一行；无 40001、无等待阻塞
```

- **为何不能用 `SKIP LOCKED`**：同一窗口若以 `SELECT ... FOR UPDATE SKIP LOCKED` 检查，S 因被 X 持锁而被**跳过** → 空集 → 静默插入重叠行；而 X 是 RC 事务、不产生 SIREAD 锁，SSI 依赖图缺边，commit 期不会收到 40001，漏判无法兜底（实证 D，回归测试同时固化了该漏判根因）。

- 部分重叠（如 A 10:00~11:00、B 10:30~11:30）同样由时间谓词 `start_at < end AND end_at > start` 命中，处理一致。
- 教室维度（同 `classroom_id`）与教师维度任一冲突即拦截。

## 3. 并发流程：时间不重叠（AC-2）

```
事务 A（教师 T，10:00~11:00）     事务 B（教师 T，12:00~13:00）
  SERIALIZABLE 冲突检查→空          SERIALIZABLE 冲突检查→空（谓词范围不相交）
  INSERT → COMMIT ✅                INSERT → COMMIT ✅
最终：两者都成功，DB 2 行（SSI 谓词锁不相交，无误伤）
```

## 4. 异常流程

### 4.1 确定性业务冲突（不重试）

- 串行或重试后冲突检查读到已存在的重叠排期 → 在事务内构造好错误消息后 `rollback`，抛 `BusinessException(400)`：
  - `该教室已被占用：YYYY-MM-DD HH:MM~HH:MM`
  - `该教师时间冲突：YYYY-MM-DD HH:MM~HH:MM`
- 该错误是确定性冲突，**立即返回、不占用重试次数**（重试也不会改变结果）。
- 注意：错误消息必须在 `rollback()` **之前**从 ORM 对象拼装——rollback 后对象过期，再访问 `c.start_at` 会触发异步惰性加载报错（greenlet_spawn）。

### 4.2 可序列化失败（自动重试，AC-3）

- 提交 / 查询阶段抛 SQLSTATE `40001`（`could not serialize access ...`）→ 记录 warning 日志，`rollback` 后以**全新快照**重新进入下一次尝试。
- 一次性冲突：第 1 次 40001 → 第 2 次成功 → 用户侧仅感知到一次正常成功。

### 4.3 重试耗尽 / 其他异常（AC-4）

- 持续 40001 直到第 3 次仍失败（或发生非 40001 异常）→ 记 error 日志，抛 `BusinessException(500)`：
  `创建排期失败，请稍后重试。若持续失败，可能是并发冲突导致。`
- 全程不向前端回传 SQL / 堆栈 / 内部主机名（经全局异常处理器统一信封）。

### 4.4 参数 / 前置校验（重试外，AC-5）

- `end_at <= start_at` → `ValidationException("结束时间必须晚于开始时间")`。
- 预约开放/截止时间晚于开始、截止早于开放 → `ValidationException`。
- `classroom_id` 指向不存在教室 → `NotFoundException("教室不存在")`；教室 `status != 1`（维护中）→ `ValidationException("该教室正在维护中，暂不可用")`。
- 这些无状态校验在进入事务 / 重试前完成，不消耗重试预算，也不产生事务开销。

## 5. 空状态 / Loading / Error / Success（前端视角）

- HTTP 契约未变，前端无需新增字段处理：
  - **Success**：`200` + 统一信封 `data`（排期对象）。
  - **冲突 400**：信封 `code=400` + `msg`（"该教师时间冲突…" / "该教室已被占用…"），前端直接 toast 展示即可。
  - **并发耗尽 500**：信封 `code=500` + 友好 `msg`，前端提示"稍后重试"。
  - **Loading**：创建按钮提交态逻辑不变；前端提交防重仍建议保留（交互体验层），最终一致性由后端事务保证。
- 前端 4 端（admin / student / teacher / miniapp）均无代码改动需求。

## 6. Permission / Authentication / Tenant

- 端点仍依赖 `Depends(get_current_user)` 与 `@require_permissions("schedule:create")`，本 Feature 不触碰鉴权。
- 租户身份来自认证后注入的 ContextVar；`find_conflicts` 内部以 `get_tenant_id()` 追加 `tenant_id` 谓词，不接受请求体传入的 `tenant_id`（符合 tenant-isolation.md）。
- 提升隔离级别 / 重试均在单租户上下文内进行，不改变租户隔离三层机制（Middleware / ContextVar / ORM 事件）。
