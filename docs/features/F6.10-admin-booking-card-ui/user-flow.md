# F6.10 用户流程：管理端预约管理与卡详情/流水 UI

> 日期：2026-10-24。契约依据 requirement.md §4（K1–K5 已核对）。

## 1. 流程总览

| 流程 | 承载端 | 说明 |
|------|--------|------|
| F-1 | admin-web 预约管理页 | 筛选 + 列表 + 代签到/完成 |
| F-2 | admin-web 会员卡详情弹窗 | 底部流水区块 |
| F-3 | teacher-web 学员列表 | 已签到学员「完成」按钮 |

---

## 2. F-1：admin-web 预约管理页流程

### 2.1 入口

```
AdminLayout 侧边栏 → 「预约管理」菜单项（排在「排期管理」之后）
  → 路由 /bookings → views/bookings/index.vue
```

### 2.2 页面加载

```
onMounted / 筛选条件变化
  → 调 bookingApi.list({ schedule_id, status, display_status, page, page_size })
  → 四态：
      loading  → el-skeleton（表格骨架）
      成功     → total === 0：el-empty「暂无预约数据」
                 total > 0：el-table 渲染
      失败     → el-result icon=error + 后端 msg + 「重试」按钮
```

### 2.3 筛选区

```
排期 ID：el-input（数字，可选；留空=不筛选）
状态多选：el-select multiple
  选项：待上课(1) / 已取消(2) / 已签到(3) / 已完成(4) / 未到场(5)
  选中后 join(',') 传入 status 参数
查询按钮：触发 fetch（重置 page=1）
重置按钮：清空筛选并重新查询
```

> 状态值对应后端 `BookingResponse.status`（1-5），label 采用学员视角文案（1 标「待上课」而非「已预约」，与 `display_status=1` 语义一致）。

### 2.4 列表列

| 列 | 字段 | 说明 |
|----|------|------|
| 学员 | `student_nickname` / `student_phone` | 昵称 + 手机号（手机号按场景展示，不脱敏，admin 端可见） |
| 课程 | `course_name` | — |
| 上课时间 | `start_at` ~ `end_at` | 本地格式化 `YYYY-MM-DD HH:mm-HH:mm` |
| 教室 | `classroom_name` | — |
| 教师 | `teacher_name` | — |
| 状态 | `display_status` → tag | 1待上课(primary) / 2已取消(info) / 3上课中(warning) / 4已完成(success)；`status=5` 未到场用 danger |
| 操作 | — | `status===1` 显示「签到」；`status===3` 显示「完成」；其余无 |

### 2.5 代签到/完成

```
点击「签到」（status===1）
  → 按钮 loading → POST /bookings/{id}/check-in
  → 成功：toast「签到成功」+ 该行 status 置 3 + 按钮切换为「完成」
  → 失败：toast 后端 msg（如「预约状态不允许签到」），按钮恢复

点击「完成」（status===3）
  → 按钮 loading → POST /bookings/{id}/complete
  → 成功：toast「完成成功」+ 该行 status 置 4 + 操作列清空
  → 失败：toast 后端 msg
```

### 2.6 分页

```
el-pagination（total / current-page / page-size）
  → current-change / size-change → 重新 fetch（保留筛选条件）
```

---

## 3. F-2：admin-web 会员卡详情弹窗流水流程

### 3.1 入口

```
会员卡列表 → 点击某行「详情」（openDetailDialog，index.vue:903-906）
  → detailDialogVisible = true，detailCard = row
```

### 3.2 流水区块加载

```
openDetailDialog 内（或 watch detailDialogVisible）
  → 调 membershipCardApi.getTransactions({ card_id: detailCard.id, page: 1, page_size: 10 })
  → 详情弹窗 el-descriptions 之后新增流水区块（约 366 行 `</el-descriptions>` 与 `</el-dialog>` 之间）
  → 四态：
      loading  → el-skeleton :rows=3
      成功     → total===0：el-empty「暂无流水记录」
                 total>0：el-table 列（操作类型/变动课时/变动后余额/备注/时间）
      失败     → 错误提示 + 重试按钮（不阻断卡详情展示）
  → 分页：el-pagination（仅流水区块内）
```

### 3.3 流水表格列

| 列 | 字段 | 格式化 |
|----|------|--------|
| 操作类型 | `operation_type` | issue→开卡 / consume→扣减 / restore→恢复 / recharge→充值 / refund→退款 / adjust→调整 / expire→过期清零 |
| 变动课时 | `change_amount` | 正数绿色 `+N`，负数红色 `-N`，0 灰色 |
| 变动后余额 | `balance_after` | — |
| 备注 | `remark` | 空显示 `-` |
| 时间 | `created_at` | `YYYY-MM-DD HH:mm` |

> 交互先例：`loadAffectedBookings`（`index.vue:750-767`）含请求序号防竞态；流水加载同构，关闭弹窗时清空状态。

---

## 4. F-3：teacher-web 学员列表「完成」按钮流程

### 4.1 现状

`teacher-web/src/views/students/index.vue`：
- `fetchData` 中状态映射：`b.status === 3 ? 'attended' : b.status === 4 ? 'completed' : 'confirmed'`（`:157`）。
- 签到按钮：`v-if="student.status === 'confirmed'"`（`:75`），调 `bookingApi.checkIn(student.id)`。

### 4.2 新增完成按钮

```
在签到按钮之后新增「完成」按钮：
  v-if="student.status === 'attended'"
  size="small" type="success" text
  @click="complete(student)"

complete(student):
  → 按钮 loading → bookingApi.complete(student.id)
  → 成功：student.status = 'completed' + toast「完成成功」
  → 失败：toast 后端 msg
```

### 4.3 状态流转

```
confirmed(status=1) --签到--> attended(status=3) --完成--> completed(status=4)
```

> 「已完成」学员无操作按钮；「已签到」学员同时不再显示签到按钮（签到按钮 `v-if="status==='confirmed'"` 已天然排除）。
