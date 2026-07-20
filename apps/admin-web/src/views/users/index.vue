<template>
  <div class="page-container">
    <div class="page-header">
      <h2>用户管理</h2>
      <el-button type="primary" @click="dialogVisible = true"><el-icon><Plus /></el-icon>新增用户</el-button>
    </div>

    <div style="display:flex;gap:12px;margin-bottom:16px">
      <el-input v-model="search" placeholder="搜索手机号/昵称" style="width:240px" clearable @keyup.enter="handleSearch" @clear="handleSearch" />
      <el-select v-model="roleFilter" placeholder="角色筛选" style="width:140px" clearable @change="handleSearch">
        <el-option label="全部" value="" />
        <el-option v-for="r in roles" :key="r.code" :label="r.name" :value="r.code" />
      </el-select>
      <el-select v-model="statusFilter" placeholder="状态筛选" style="width:140px" clearable @change="handleSearch">
        <el-option label="全部" value="" />
        <el-option label="正常" value="active" />
        <el-option label="禁用" value="disabled" />
      </el-select>
    </div>

    <el-table :data="users" stripe v-loading="loading" style="width:100%">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="nickname" label="昵称">
        <template #default="{ row }">{{ row.nickname || '-' }}</template>
      </el-table-column>
      <el-table-column prop="phone" label="手机号" width="140" />
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">{{ row.status === 1 ? '正常' : '禁用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="注册时间" width="180">
        <template #default="{ row }">{{ row.created_at?.slice(0, 10) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" link @click="handleEdit(row)">编辑</el-button>
          <el-button type="warning" size="small" link @click="handleResetPwd(row)">重置密码</el-button>
          <el-button type="danger" size="small" link @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div style="display:flex;justify-content:center;margin-top:20px">
      <el-pagination
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="handlePageChange"
      />
    </div>

    <el-dialog v-model="dialogVisible" title="新增用户" width="480px" :close-on-click-modal="false">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="请输入手机号" maxlength="11" />
        </el-form-item>
        <el-form-item label="昵称" prop="nickname">
          <el-input v-model="form.nickname" placeholder="请输入昵称" maxlength="20" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="请输入密码（至少6位）" show-password />
        </el-form-item>
        <el-form-item label="角色" prop="roleCodes">
          <el-select v-model="form.roleCodes" multiple placeholder="请选择角色" style="width:100%">
            <el-option v-for="r in roles" :key="r.code" :label="r.name" :value="r.code" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editVisible" title="编辑用户" width="480px" :close-on-click-modal="false">
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="80px">
        <el-form-item label="手机号">
          <el-input :model-value="editForm.phone" disabled />
        </el-form-item>
        <el-form-item label="昵称" prop="nickname">
          <el-input v-model="editForm.nickname" placeholder="请输入昵称" maxlength="20" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="editForm.status" style="width:100%">
            <el-option label="正常" :value="1" />
            <el-option label="禁用" :value="0" />
          </el-select>
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="editForm.roleCodes" multiple placeholder="请选择角色" style="width:100%">
            <el-option v-for="r in roles" :key="r.code" :label="r.name" :value="r.code" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editLoading" @click="handleEditSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="pwdVisible" title="重置密码" width="420px" :close-on-click-modal="false">
      <el-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" label-width="80px">
        <el-form-item label="用户">
          <el-input :model-value="pwdTarget?.nickname || pwdTarget?.phone || ''" disabled />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input v-model="pwdForm.newPassword" type="password" placeholder="请输入新密码（至少6位）" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdVisible = false">取消</el-button>
        <el-button type="primary" :loading="pwdLoading" @click="handlePwdSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { userApi, roleApi, type User } from '@dance-saas/api-client'

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
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
}

const editForm = reactive({
  phone: '',
  nickname: '',
  status: 1 as number,
  roleCodes: [] as string[],
})

const editRules: FormRules = {
  nickname: [
    { required: true, message: '请输入昵称', trigger: 'blur' },
  ],
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
  } catch { /* ignore */ }
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
  try {
    await ElMessageBox.confirm(
      `确定要删除用户 "${user.nickname || user.phone}" 吗？`,
      '删除确认',
      { type: 'warning' }
    )
    await userApi.delete(user.id)
    ElMessage.success('删除成功')
    fetchUsers()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.msg || '删除失败')
    }
  }
}

function handleEdit(user: User) {
  editId.value = user.id
  editForm.phone = user.phone
  editForm.nickname = user.nickname || ''
  editForm.status = user.status
  editForm.roleCodes = user.roles || []
  editVisible.value = true
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
      payload.role_ids = roles.value
        .filter(r => editForm.roleCodes.includes(r.code))
        .map(r => r.id)
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