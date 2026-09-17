<template>
  <div class="page-container">
    <div class="page-header">
      <h2>用户管理</h2>
      <el-button type="primary" @click="openCreateDialog"> 新增 </el-button>
    </div>

    <div style="display: flex; gap: 12px; margin-bottom: 16px">
      <el-input
        v-model="search"
        placeholder="搜索手机号/昵称"
        style="width: 240px"
        clearable
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      >
        <template #suffix>
          <el-icon class="search-icon" style="cursor: pointer" @click="handleSearch">
            <Search />
          </el-icon>
        </template>
      </el-input>
      <el-select
        v-model="roleFilter"
        placeholder="角色筛选"
        style="width: 140px"
        clearable
        @change="handleSearch"
      >
        <el-option label="全部" value="" />
        <el-option v-for="r in roles" :key="r.code" :label="r.name" :value="r.code" />
      </el-select>
      <el-select
        v-model="statusFilter"
        placeholder="状态筛选"
        style="width: 140px"
        clearable
        @change="handleSearch"
      >
        <el-option label="全部" value="" />
        <el-option label="正常" value="active" />
        <el-option label="禁用" value="disabled" />
      </el-select>
    </div>

    <el-table v-loading="loading" :data="users" stripe style="width: 100%">
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="nickname" label="昵称">
        <template #default="{ row }">
          {{ row.nickname || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="phone" label="手机号" width="140" />
      <el-table-column prop="teacher_code" label="教师编号" width="160">
        <template #default="{ row }">
          {{ row.teacher_code || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="student_code" label="学员编号" width="160">
        <template #default="{ row }">
          {{ row.student_code || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
            {{ row.status === 1 ? '正常' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="wechat_bound" label="微信绑定" width="100">
        <template #default="{ row }">
          <el-tag :type="row.wechat_bound ? 'success' : 'info'" size="small">
            {{ row.wechat_bound ? '已绑定' : '未绑定' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="注册时间" width="180">
        <template #default="{ row }">
          {{ row.created_at?.slice(0, 10) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="380" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" link @click="handleEdit(row)"> 编辑 </el-button>
          <el-button type="warning" size="small" link @click="handleResetPwd(row)">
            重置密码
          </el-button>
          <el-button type="danger" size="small" link @click="handleDelete(row)"> 删除 </el-button>
          <el-button
            v-if="row.wechat_bound"
            type="danger"
            size="small"
            link
            @click="handleUnbindWechat(row)"
          >
            解绑微信
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrapper">
      <el-pagination
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="handlePageChange"
      />
    </div>

    <el-dialog v-model="dialogVisible" title="新增" width="480px" :close-on-click-modal="false">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="请输入手机号" maxlength="11" />
        </el-form-item>
        <el-form-item label="昵称" prop="nickname">
          <el-input v-model="form.nickname" placeholder="请输入昵称" maxlength="20" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码（至少6位）"
            show-password
          />
        </el-form-item>
        <el-form-item label="角色" prop="roleCodes">
          <el-select v-model="form.roleCodes" multiple placeholder="请选择角色" style="width: 100%">
            <el-option v-for="r in roles" :key="r.code" :label="r.name" :value="r.code" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false"> 取消 </el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit"> 确定 </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editVisible" title="编辑" width="480px" :close-on-click-modal="false">
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="80px">
        <el-form-item label="手机号">
          <el-input :model-value="editForm.phone" disabled />
        </el-form-item>
        <el-form-item label="昵称" prop="nickname">
          <el-input v-model="editForm.nickname" placeholder="请输入昵称" maxlength="20" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="editForm.status" style="width: 100%">
            <el-option label="正常" :value="1" />
            <el-option label="禁用" :value="0" />
          </el-select>
        </el-form-item>
        <el-form-item label="角色" prop="roleCodes">
          <el-select
            v-model="editForm.roleCodes"
            multiple
            placeholder="请选择角色"
            style="width: 100%"
          >
            <el-option v-for="r in roles" :key="r.code" :label="r.name" :value="r.code" />
          </el-select>
          <div class="form-tip">⚠️ 修改角色将自动同步教师/学员档案，历史数据将保留</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false"> 取消 </el-button>
        <el-button type="primary" :loading="editLoading" @click="handleEditSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="pwdVisible" title="重置密码" width="420px" :close-on-click-modal="false">
      <el-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" label-width="80px">
        <el-form-item label="用户">
          <el-input :model-value="pwdTarget?.nickname || pwdTarget?.phone || ''" disabled />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input
            v-model="pwdForm.newPassword"
            type="password"
            placeholder="请输入新密码（至少6位）"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdVisible = false"> 取消 </el-button>
        <el-button type="primary" :loading="pwdLoading" @click="handlePwdSubmit"> 确定 </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { roleApi, userApi, type User } from '@dance-saas/api-client'
import { Search } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

const loading = ref(false)
const submitLoading = ref(false)
const search = ref('')
const roleFilter = ref('')
const statusFilter = ref('')
const dialogVisible = ref(false)
const editVisible = ref(false)
const pwdVisible = ref(false)
const editLoading = ref(false)
const pwdLoading = ref(false)
const editId = ref(0)
const pwdTarget = ref<User | null>(null)
const users = ref<User[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const roles = ref<{ id: number; code: string; name: string }[]>([])
const formRef = ref<FormInstance>()
const editFormRef = ref<FormInstance>()
const pwdFormRef = ref<FormInstance>()

const form = reactive({
  phone: '',
  nickname: '',
  password: '',
  roleCodes: [] as string[],
})

const rules: FormRules = {
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '手机号格式不正确', trigger: 'blur' },
  ],
  nickname: [{ required: true, message: '请输入昵称', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
  roleCodes: [{ required: true, message: '请选择角色', trigger: 'change', type: 'array' as const }],
}

const editForm = reactive({
  phone: '',
  nickname: '',
  status: 1 as number,
  roleCodes: [] as string[],
})

const editRules: FormRules = {
  nickname: [{ required: true, message: '请输入昵称', trigger: 'blur' }],
  roleCodes: [{ required: true, message: '请选择角色', trigger: 'change', type: 'array' as const }],
}

const pwdForm = reactive({
  newPassword: '',
})

const pwdRules: FormRules = {
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
}

function resetForm() {
  form.phone = ''
  form.nickname = ''
  form.password = ''
  form.accountType = 'teacher'
  form.roleCodes = []
  formRef.value?.resetFields()
}

function handleSearch() {
  page.value = 1
  fetchUsers()
}

async function fetchUsers() {
  loading.value = true
  try {
    const res = await userApi.list({
      page: page.value,
      page_size: pageSize.value,
      keyword: search.value || undefined,
      role_code: roleFilter.value || undefined,
      status: statusFilter.value ? (statusFilter.value === 'active' ? 1 : 0) : undefined,
    })
    users.value = res.data.items
    total.value = res.data.total
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '加载用户列表失败')
  } finally {
    loading.value = false
  }
}

async function fetchRoles() {
  try {
    const res = await roleApi.list({ page_size: 100 })
    roles.value = res.data.items
  } catch {
    /* ignore */
  }
}

function openCreateDialog() {
  resetForm()
  dialogVisible.value = true
  formRef.value?.clearValidate()
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitLoading.value = true
  try {
    await userApi.create({
      phone: form.phone,
      password: form.password,
      nickname: form.nickname || undefined,
      role_codes: form.roleCodes.length > 0 ? form.roleCodes : undefined,
    })
    ElMessage.success('新增用户成功')
    dialogVisible.value = false
    resetForm()
    fetchUsers()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '新增用户失败')
  } finally {
    submitLoading.value = false
  }
}

async function handleDelete(user: User) {
  const hasTeacherRole = user.roles?.includes('teacher')
  const hasStudentRole = user.roles?.includes('student')

  let warningMessage = `确定要删除用户 "<strong>${user.nickname || user.phone}</strong>" 吗？<br/><br/>`

  const impacts: string[] = []

  if (hasTeacherRole) {
    impacts.push('• 清除教师档案（教师编号、个人简介、专长、教学经验等）')
    impacts.push('• 该教师的历史排课记录、课程评价等数据将无法关联查看')
  }

  if (hasStudentRole) {
    impacts.push('• 清除学员档案（学员编号、紧急联系人、学习等级、标签等）')
    impacts.push('• 该学员的预约记录、课程历史、学习进度等数据将无法关联查看')
  }

  if (impacts.length > 0) {
    warningMessage += '⚠️ 删除后将清除以下关联信息：<br/>' + impacts.join('<br/>') + '<br/><br/>'
    warningMessage += '🔒 此操作不可恢复，请谨慎操作！'
  } else {
    warningMessage += '此操作不可恢复，请谨慎操作！'
  }

  try {
    await ElMessageBox.confirm(warningMessage, '删除确认', {
      type: 'warning',
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
      dangerouslyUseHTMLString: true,
      customClass: 'delete-confirm-dialog',
    })
    await userApi.delete(user.id)
    ElMessage.success('删除成功')
    fetchUsers()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.msg || '删除失败')
    }
  }
}

async function handleUnbindWechat(user: User) {
  const hasStudentRole = user.roles?.includes('student')
  const hasTeacherRole = user.roles?.includes('teacher')
  const hasAdminRole = user.roles?.includes('admin') || user.roles?.includes('super_admin')

  let warningMessage = `确定要解除用户 "<strong>${user.nickname || user.phone}</strong>" 的微信绑定吗？<br/><br/>`

  const impacts: string[] = []
  impacts.push('• 解绑后该用户将无法使用微信一键登录')

  if (hasStudentRole && !hasTeacherRole && !hasAdminRole) {
    // 只有学员角色
    impacts.push('• 该用户仅有学员权限，解绑后将无法登录学员端小程序')
    impacts.push('• 需要重新绑定微信后才能继续使用小程序')
  } else if (hasStudentRole) {
    // 有学员角色和其他角色
    impacts.push('• 该用户拥有学员权限，解绑后将无法使用微信登录学员端小程序')
    impacts.push('• 但仍可通过手机号+密码登录管理后台')
  } else {
    // 没有学员角色
    impacts.push('• 该用户没有学员权限，解绑后不影响其他功能使用')
  }

  warningMessage += impacts.join('<br/>')

  try {
    await ElMessageBox.confirm(warningMessage, '解绑微信确认', {
      type: 'warning',
      confirmButtonText: '确定解绑',
      cancelButtonText: '取消',
      dangerouslyUseHTMLString: true,
    })
    await userApi.unbindWechat(user.id)
    ElMessage.success('微信解绑成功')
    fetchUsers()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.msg || '解绑失败')
    }
  }
}

function handleEdit(user: User) {
  editId.value = user.id
  editForm.phone = user.phone
  editForm.nickname = user.nickname || ''
  editForm.status = user.status
  editForm.roleCodes = user.roles || []

  // 根据用户现有角色推断账号类型
  const userRoles = user.roles || []
  if (userRoles.includes('admin') || userRoles.includes('super_admin')) {
    editForm.accountType = 'admin'
  } else if (userRoles.includes('teacher')) {
    editForm.accountType = 'teacher'
  } else if (userRoles.includes('student')) {
    editForm.accountType = 'student'
  } else {
    editForm.accountType = 'teacher' // 默认
  }

  editVisible.value = true
  editFormRef.value?.clearValidate()
}

async function handleEditSubmit() {
  const valid = await editFormRef.value?.validate().catch(() => false)
  if (!valid) return

  editLoading.value = true
  try {
    const payload: any = {
      nickname: editForm.nickname || undefined,
      status: editForm.status,
    }
    if (editForm.roleCodes.length > 0) {
      payload.role_ids = roles.value.filter(r => editForm.roleCodes.includes(r.code)).map(r => r.id)
    }
    await userApi.update(editId.value, payload)
    ElMessage.success('编辑成功')
    editVisible.value = false
    fetchUsers()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '编辑失败')
  } finally {
    editLoading.value = false
  }
}

function handleResetPwd(user: User) {
  pwdTarget.value = user
  pwdForm.newPassword = ''
  pwdFormRef.value?.resetFields()
  pwdVisible.value = true
  pwdFormRef.value?.clearValidate()
}

async function handlePwdSubmit() {
  const valid = await pwdFormRef.value?.validate().catch(() => false)
  if (!valid) return
  if (!pwdTarget.value) return

  pwdLoading.value = true
  try {
    await userApi.resetPassword(pwdTarget.value.id, pwdForm.newPassword)
    ElMessage.success('密码重置成功')
    pwdVisible.value = false
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '重置密码失败')
  } finally {
    pwdLoading.value = false
  }
}

function handlePageChange(p: number) {
  page.value = p
  fetchUsers()
}

onMounted(() => {
  fetchUsers()
  fetchRoles()
})
</script>

<style scoped>
.search-icon:hover {
  color: #409eff;
}
</style>