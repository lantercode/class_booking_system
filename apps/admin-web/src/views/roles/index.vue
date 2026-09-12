<template>
  <div class="page-container">
    <div class="page-header">
      <h2>角色权限</h2>
    </div>

    <div class="roles-layout">
      <!-- 左侧：角色列表 -->
      <div class="role-list-panel">
        <div class="panel-header">
          <h3>角色列表</h3>
          <el-button type="primary" size="small" text @click="openCreateDialog">
            新增
          </el-button>
        </div>
        <div class="role-list">
          <div v-for="role in roles" :key="role.id" class="role-item" :class="{ active: selectedRole?.id === role.id }" @click="selectRole(role)">
            <div class="role-info">
              <span class="role-name">{{ role.name }}</span>
              <span class="role-code">{{ role.code }}</span>
            </div>
            <div class="role-actions">
              <el-tag v-if="role.is_system" size="small" type="info">系统</el-tag>
              <el-button
                v-if="!role.is_system"
                size="small"
                type="danger"
                text
                :loading="deleteLoading === role.id"
                @click.stop="handleDeleteRole(role)"
              >
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：权限配置 -->
      <div class="permission-panel" v-loading="loading">
        <div class="panel-header">
          <span style="font-weight:600">{{ selectedRole ? selectedRole.name + ' - 权限配置' : '请选择角色' }}</span>
          <el-tag v-if="selectedRole?.is_system && !isSuperAdmin" type="warning" size="small">系统角色不可修改</el-tag>
          <el-tag v-else-if="selectedRole?.is_system && isSuperAdmin" type="success" size="small">超级管理员可修改</el-tag>
        </div>
        <div class="permission-content">
          <el-tree
            v-if="selectedRole"
            ref="treeRef"
            :key="selectedRole.id"
            :data="treeData"
            show-checkbox
            node-key="id"
            default-expand-all
            :default-checked-keys="checkedKeys"
            :check-strictly="false"
            :disabled="isPermissionTreeDisabled"
            @check="handleCheck"
          />
          <el-empty v-else description="点击左侧角色查看权限" />
        </div>
      </div>
    </div>

    <el-dialog v-model="showRoleDialog" title="新增" width="480px" :close-on-click-modal="false">
      <el-form ref="roleFormRef" :model="roleForm" :rules="roleRules" label-width="80px">
        <el-form-item label="角色代码" prop="code">
          <el-input v-model="roleForm.code" placeholder="英文标识，如 editor" maxlength="50" />
        </el-form-item>
        <el-form-item label="角色名称" prop="name">
          <el-input v-model="roleForm.name" placeholder="如：编辑员" maxlength="50" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="roleForm.description" placeholder="可选" maxlength="255" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRoleDialog = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="handleCreateRole">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { Plus, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import type { ElTree } from 'element-plus'
import { roleApi, type Role } from '@dance-saas/api-client'

const loading = ref(false)
const saving = ref(false)
const showRoleDialog = ref(false)
const createLoading = ref(false)
const deleteLoading = ref<number | null>(null)
const roleFormRef = ref<FormInstance>()
const treeRef = ref<InstanceType<typeof ElTree>>()
const selectedRole = ref<Role | null>(null)
const roles = ref<Role[]>([])
const allPermissions = ref<{ id: number; code: string; name: string; module: string }[]>([])
const rolePermissionIds = ref<number[]>([])

// 判断当前用户是否为超级管理员
const isSuperAdmin = computed(() => {
  try {
    const info = JSON.parse(localStorage.getItem('adminInfo') || '{}')
    return info.roles?.includes('super_admin')
  } catch {
    return false
  }
})

// 判断当前选中的角色是否为系统角色且当前用户不是超级管理员
const isPermissionTreeDisabled = computed(() => {
  return selectedRole.value?.is_system && !isSuperAdmin.value
})

const roleForm = ref({
  code: '',
  name: '',
  description: '',
})

const roleRules: FormRules = {
  code: [
    { required: true, message: '请输入角色代码', trigger: 'blur' },
    { pattern: /^[a-zA-Z][a-zA-Z0-9_]*$/, message: '字母开头，仅允许字母数字下划线', trigger: 'blur' },
  ],
  name: [
    { required: true, message: '请输入角色名称', trigger: 'blur' },
  ],
}

function openCreateDialog() {
  roleForm.value = { code: '', name: '', description: '' }
  roleFormRef.value?.resetFields()
  showRoleDialog.value = true
}

async function handleCreateRole() {
  const valid = await roleFormRef.value?.validate().catch(() => false)
  if (!valid) return

  createLoading.value = true
  try {
    await roleApi.create({
      code: roleForm.value.code,
      name: roleForm.value.name,
      description: roleForm.value.description || undefined,
    })
    ElMessage.success('角色创建成功')
    showRoleDialog.value = false
    fetchRoles()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '创建角色失败')
  } finally {
    createLoading.value = false
  }
}

async function handleDeleteRole(role: Role) {
  try {
    await ElMessageBox.confirm(
      `确定删除角色「${role.name}」吗？删除后不可恢复。`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }

  deleteLoading.value = role.id
  try {
    await roleApi.delete(role.id)
    ElMessage.success('角色已删除')
    if (selectedRole.value?.id === role.id) {
      selectedRole.value = null
    }
    fetchRoles()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '删除角色失败')
  } finally {
    deleteLoading.value = null
  }
}

async function fetchRoles() {
  try {
    const res = await roleApi.list({ page_size: 100 })
    roles.value = res.data.items
    if (!selectedRole.value && roles.value.length > 0) {
      selectRole(roles.value[0])
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '加载角色列表失败')
  }
}

async function fetchAllPermissions() {
  try {
    const res = await roleApi.listPermissions()
    allPermissions.value = res.data.items
  } catch (_) {}
}

async function selectRole(role: Role) {
  rolePermissionIds.value = []
  selectedRole.value = role
  loading.value = true
  try {
    const res = await roleApi.getPermissions(role.id)
    rolePermissionIds.value = res.data.items.map((p: any) => p.id)
    await nextTick()
    treeRef.value?.setCheckedKeys(rolePermissionIds.value)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '加载角色权限失败')
  } finally {
    loading.value = false
  }
}

const treeData = computed(() => {
  const moduleMap = new Map<string, { id: string; label: string; children: { id: number; label: string }[] }>()
  const moduleNames: Record<string, string> = {
    user: '用户管理',
    course: '课程管理',
    schedule: '排课管理',
    booking: '预约管理',
    classroom: '教室管理',
    role: '角色权限',
    billing: '计费管理',
    dashboard: '仪表盘',
  }
  for (const p of allPermissions.value) {
    if (!moduleMap.has(p.module)) {
      moduleMap.set(p.module, {
        id: `module-${p.module}`,
        label: moduleNames[p.module] || p.module,
        children: [],
      })
    }
    moduleMap.get(p.module)!.children.push({
      id: p.id,
      label: p.name,
    })
  }
  return Array.from(moduleMap.values())
})

const checkedKeys = computed(() => {
  return rolePermissionIds.value
})

async function handleCheck(_node: any, checked: { checkedKeys: (number | string)[] }) {
  if (!selectedRole.value) return
  const permissionIds = checked.checkedKeys.filter((id): id is number => typeof id === 'number')
  const previousIds = [...rolePermissionIds.value]
  
  saving.value = true
  try {
    await roleApi.assignPermissions(selectedRole.value.id, permissionIds)
    rolePermissionIds.value = permissionIds
    ElMessage.success('权限已更新')
  } catch (e: any) {
    // 失败时回滚勾选状态
    rolePermissionIds.value = previousIds
    await nextTick()
    treeRef.value?.setCheckedKeys(previousIds)
    ElMessage.error(e?.response?.data?.msg || '保存权限失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  fetchRoles()
  fetchAllPermissions()
})
</script>

<style scoped lang="scss">
.page-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.roles-layout {
  display: flex;
  gap: 20px;
  margin-top: 16px;
  align-items: stretch;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* ===== 左侧角色列表面板 ===== */
.role-list-panel {
  width: 280px;
  flex-shrink: 0;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #ebeef5;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.role-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;

  /* 自定义滚动条样式 */
  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: #dcdfe6;
    border-radius: 2px;
    transition: background 0.3s;
  }

  &::-webkit-scrollbar-thumb:hover {
    background: #c0c4cc;
  }
}

/* ===== 右侧权限配置面板 ===== */
.permission-panel {
  flex: 1;
  min-width: 0;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #ebeef5;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.permission-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;

  :deep(.el-tree) {
    min-height: 100%;
  }

  /* 自定义滚动条样式 */
  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: #dcdfe6;
    border-radius: 2px;
    transition: background 0.3s;
  }

  &::-webkit-scrollbar-thumb:hover {
    background: #c0c4cc;
  }
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;

  h3 {
    font-size: 15px;
    font-weight: 600;
    color: #303133;
    margin: 0;
  }
}

.role-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
  margin-bottom: 4px;

  &:hover { background: #f5f7fa; }
  &.active { background: #ecf5ff; border-left: 3px solid #667eea; }

  .role-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }

  .role-info {
    .role-name { font-size: 14px; font-weight: 500; color: #303133; display: block; }
    .role-code { font-size: 12px; color: #909399; }
  }
}
</style>