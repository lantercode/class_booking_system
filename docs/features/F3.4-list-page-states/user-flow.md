# F3.4 — User Flow

四态面向真实用户操作场景，参考 [tenant/index.vue](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/tenant/index.vue) 已落地的 F3.3 样板。

## Flow 1：首次进入 → loading → success

1. 用户进入列表页（如 `/admin/membership`）；
2. `onMounted` 触发 `fetchXxx()`，`loading.value = true`；
3. 容器 `v-loading="loading"` 显示加载遮罩（admin-web：el-table 上直接 v-loading；teacher-web/schedule：calendar-card 上 v-loading；teacher-web/students：state-wrapper + v-loading）；
4. 接口成功返回，`loading.value = false`，列表渲染 → success 态。

## Flow 2：进入空列表 → loading → empty

1. 用户进入列表页；
2. loading 遮罩显示；
3. 接口返回空列表（items.length === 0）；
4. 进入 empty 分支：
   - admin-web el-table：`empty-text="暂无数据"` 自动渲染空态；
   - student-web/teacher-web：`v-else-if list.length === 0` 显示 `<el-empty description="暂无 X" />`；
5. 若提供创建入口（如 teacher-web/courses empty 态有"创建第一门课程"按钮），用户可点击跳转创建页。

## Flow 3：接口失败 → loading → error → 重试 → success

1. 用户进入列表页；
2. loading 遮罩显示；
3. 后端返回 4xx/5xx（如网络异常、权限不足、租户失效）；
4. catch 块执行：
   ```ts
   catch (e: any) {
     loadError.value = e?.response?.data?.msg || '加载 X 列表失败'
     ElMessage.error(loadError.value)
     list.value = []
   }
   ```
5. `loading.value = false`，容器进入 error 分支：
   ```html
   <div v-if="loadError" class="error-block">
     <el-result icon="error" title="加载 X 列表失败" :sub-title="loadError">
       <template #extra>
         <el-button type="primary" @click="fetchXxx">重试</el-button>
       </template>
     </el-result>
   </div>
   ```
6. 用户点击"重试" → 重新执行 `fetchXxx()` → loading → success / empty / error 循环；
7. 同步顶部 toast `ElMessage.error` 显示后端返回的 msg（统一信封 `{code, msg, data}` 中的 msg）。

## Flow 4：双面板切换（admin-web/roles）

1. 用户进入 `/admin/roles`，左侧 role-list 加载（`roleLoading`）；
2. 选中某个角色后，右侧 permission-content 加载该角色的权限树（`permLoadError`）；
3. 任一面加载失败均显示 `el-result` + 重试：
   - 左侧重试 → `fetchRoles()`；
   - 右侧重试 → `selectRole(selectedRole)` 复用当前角色上下文。

## Flow 5：Dashboard（admin-web/dashboard）

1. 用户进入 `/admin/dashboard`，`fetchDashboard()` 并行加载统计与最近列表；
2. 整个 dashboard-content 容器 `v-loading` 显示加载态；
3. 失败时显示 `el-result` + 重试（重试整个 fetchDashboard）；
4. 成功时两个 el-table（最近课程 / 最近学员）各自 `empty-text="暂无数据"`。
