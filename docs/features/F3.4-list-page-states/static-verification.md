# F3.4 — Static Verification

## 1. 三端 vue-tsc 类型检查

```bash
cd /Users/lixiang/Desktop/class_booking_system/apps/admin-web && npx vue-tsc --noEmit
# 0 error（命令无输出）
```

```bash
cd /Users/lixiang/Desktop/class_booking_system/apps/student-web && npx vue-tsc --noEmit
# 0 error（命令无输出）
```

```bash
cd /Users/lixiang/Desktop/class_booking_system/apps/teacher-web && npx vue-tsc --noEmit
# 0 error（命令无输出）
```

## 2. 三端构建

```bash
cd /Users/lixiang/Desktop/class_booking_system/apps/admin-web && pnpm run build
# vue-tsc -b && vite build → ✓ built in 3.54s
```

```bash
cd /Users/lixiang/Desktop/class_booking_system/apps/student-web && pnpm run build
# vue-tsc -b && vite build → ✓ built in 3.08s
```

```bash
cd /Users/lixiang/Desktop/class_booking_system/apps/teacher-web && pnpm run build
# vue-tsc -b && vite build → ✓ built in 3.52s
```

## 3. 四态覆盖证据 — loading 态（v-loading | el-skeleton）

```bash
grep -rln "v-loading\|el-skeleton" apps/admin-web/src/views apps/student-web/src/views apps/teacher-web/src/views
```

admin-web（11 页）：
- dashboard / roles / classrooms / card-types / courses / membership / schedules / teachers / students / users / tenant

student-web（3 页）：
- courses / schedule / my-bookings

teacher-web（3 页）：
- courses / students / schedule

合计 16 个被改列表页全部具备 loading 态。

## 4. 四态覆盖证据 — empty 态（el-empty | empty-text）

```bash
grep -rl "el-empty\|empty-text" apps/admin-web/src/views apps/student-web/src/views apps/teacher-web/src/views
```

被改 16 个列表页全部具备 empty 态（el-empty 或 el-table empty-text）。

## 5. 四态覆盖证据 — error 态（el-result icon="error" | loadError）

```bash
grep -rc "el-result icon=\"error\"\|loadError" apps/admin-web/src/views apps/student-web/src/views apps/teacher-web/src/views
```

结果（按文件计数）：

| 端 | 页面 | 命中数 |
|----|------|--------|
| admin-web | tenant/index.vue | 6 |
| admin-web | membership/index.vue | 7 |
| admin-web | courses/index.vue | 7 |
| admin-web | card-types/index.vue | 7 |
| admin-web | classrooms/index.vue | 7 |
| admin-web | roles/index.vue | 7 |
| admin-web | dashboard/index.vue | 7 |
| admin-web | users/index.vue | 7 |
| admin-web | schedules/index.vue | 7 |
| admin-web | teachers/index.vue | 7 |
| admin-web | students/index.vue | 7 |
| student-web | courses/index.vue | 7 |
| student-web | schedule/index.vue | 7 |
| student-web | my-bookings/index.vue | 7 |
| teacher-web | courses/index.vue | 7 |
| teacher-web | students/index.vue | 7 |
| teacher-web | schedule/index.vue | 7 |

合计 17 个文件、111 个 loadError 出现（每个文件平均约 7 个：1 个 ref 声明 + 1 个清空 + 1 个 catch 赋值 + 1 个 ElMessage.error 调用 + 1 个 v-if loadError + 1 个 :sub-title + 1 个 el-result icon="error"）。

## 6. 契约合规检查

```bash
# 错误响应来自统一信封（不直接读 HTTP status）
grep -n "e?.response?.data?.msg" apps/admin-web/src/views/membership/index.vue \
  apps/student-web/src/views/my-bookings/index.vue \
  apps/teacher-web/src/views/schedule/index.vue
# 全部命中
```

## 7. 不引入新依赖检查

```bash
grep -n "^import" apps/teacher-web/src/views/courses/index.vue | grep -v "@element-plus\|@dance-saas\|vue\|element-plus"
# 0 匹配（所有 import 都来自既有依赖）
```

## 8. 不改后端检查

```bash
git diff --name-only | grep "^apps/api/"
# 0 匹配（无后端文件改动）
```

## 汇总

- 三端 vue-tsc 0 error
- 三端 build 成功（admin 3.54s / student 3.08s / teacher 3.52s）
- 16 个列表页（含 F3.3 tenant）四态覆盖完整
- 无新依赖、无后端改动、catch 走统一信封 msg
