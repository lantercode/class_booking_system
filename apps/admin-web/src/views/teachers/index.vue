<template>
  <div class="page-container">
    <div class="page-header">
      <h2>教师管理</h2>
      <el-button type="primary" @click="openCreateDialog"><el-icon><Plus /></el-icon>新增教师</el-button>
    </div>

    <div style="display:flex;gap:12px;margin-bottom:16px">
      <el-input v-model="search" placeholder="搜索姓名/手机号" style="width:240px" clearable @keyup.enter="handleSearch" @clear="handleSearch" />
      <el-select v-model="statusFilter" placeholder="状态筛选" style="width:140px" clearable @change="handleSearch">
        <el-option label="全部" value="" />
        <el-option label="正常" value="active" />
        <el-option label="禁用" value="disabled" />
      </el-select>
    </div>

    <el-table :data="filteredTeachers" stripe v-loading="loading" style="width:100%">
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="name" label="姓名" />
      <el-table-column prop="phone" label="手机号" width="140" />
      <el-table-column prop="speciality" label="专长" width="100" />
      <el-table-column prop="status" label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'danger'" size="small">{{ row.status === 'active' ? '正常' : '禁用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="courseCount" label="课程数" width="80" />
      <el-table-column prop="studentCount" label="学员数" width="80" />
      <el-table-column prop="rating" label="评分" width="80" />
      <el-table-column prop="joinedAt" label="加入时间" width="120" />
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" link @click="handleEdit(row)">编辑</el-button>
          <el-button
            v-if="row.status === 'active'"
            type="danger"
            size="small"
            link
            :loading="toggleLoading === row.id"
            @click="handleToggleStatus(row)"
          >禁用</el-button>
          <el-button
            v-else
            type="success"
            size="small"
            link
            :loading="toggleLoading === row.id"
            @click="handleToggleStatus(row)"
          >启用</el-button>
          <el-button
            type="danger"
            size="small"
            link
            :loading="deleteLoading === row.id"
            @click="handleDelete(row)"
          >删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="createVisible" title="新增教师" width="480px" :close-on-click-modal="false">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="80px">
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="createForm.phone" placeholder="请输入手机号" maxlength="11" />
        </el-form-item>
        <el-form-item label="昵称" prop="nickname">
          <el-input v-model="createForm.nickname" placeholder="请输入昵称" maxlength="20" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="createForm.password" type="password" placeholder="请输入密码（至少6位）" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="handleCreateSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editVisible" title="编辑教师" width="480px" :close-on-click-modal="false">
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
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editLoading" @click="handleEditSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { userApi, type User } from '@dance-saas/api-client'

const search = ref('')
const statusFilter = ref('')
const loading = ref(false)
const createLoading = ref(false)
const editLoading = ref(false)
const toggleLoading = ref<number | null>(null)
const deleteLoading = ref<number | null>(null)
const users = ref<User[]>([])

const createVisible = ref(false)
const editVisible = ref(false)
const createFormRef = ref<FormInstance>()
const editFormRef = ref<FormInstance>()
const editId = ref(0)

const createForm = ref({
  phone: '',
  nickname: '',
  password: '',
})

const createRules: FormRules = {
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '手机号格式不正确', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
}

const editForm = ref({
  phone: '',
  nickname: '',
  status: 1 as number,
})

const editRules: FormRules = {
  nickname: [
    { required: true, message: '请输入昵称', trigger: 'blur' },
  ],
}

const teachers = computed(() => {
  return users.value.filter(u => u.roles.includes('teacher'))
})

const filteredTeachers = computed(() => {
  return teachers.value.filter(t => {
    const name = t.nickname || t.phone
    if (search.value && !name.includes(search.value) && !t.phone.includes(search.value)) return false
    if (statusFilter.value === 'active' && t.status !== 1) return false
    if (statusFilter.value === 'disabled' && t.status !== 0) return false
    return true
  }).map(t => ({
    id: t.id,
    name: t.nickname || t.phone,
    phone: t.phone,
    speciality: '暂无',
    status: t.status === 1 ? ('active' as const) : ('disabled' as const),
    courseCount: 0,
    studentCount: 0,
    rating: '暂无',
    joinedAt: t.created_at?.slice(0, 10) || '',
  }))
})

async function fetchUsers() {
  loading.value = true
  try {
    const res = await userApi.list({ page_size: 100, role_code: 'teacher' })
    users.value = res.data.items
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '加载用户列表失败')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  fetchUsers()
}

function openCreateDialog() {
  createForm.value = { phone: '', nickname: '', password: '' }
  createFormRef.value?.resetFields()
  createVisible.value = true
}

async function handleCreateSubmit() {
  const valid = await createFormRef.value?.validate().catch(() => false)
  if (!valid) return

  createLoading.value = true
  try {
    await userApi.create({
      phone: createForm.value.phone,
      password: createForm.value.password,
      nickname: createForm.value.nickname || undefined,
      role_codes: ['teacher'],
    })
    ElMessage.success('新增教师成功')
    createVisible.value = false
    fetchUsers()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '新增教师失败')
  } finally {
    createLoading.value = false
  }
}

function handleEdit(row: { id: number; phone: string; name: string; status: string }) {
  editId.value = row.id
  editForm.value = {
    phone: row.phone,
    nickname: row.name,
    status: row.status === 'active' ? 1 : 0,
  }
  editFormRef.value?.resetFields()
  editVisible.value = true
}

async function handleEditSubmit() {
  const valid = await editFormRef.value?.validate().catch(() => false)
  if (!valid) return

  editLoading.value = true
  try {
    await userApi.update(editId.value, {
      nickname: editForm.value.nickname || undefined,
      status: editForm.value.status,
    })
    ElMessage.success('编辑成功')
    editVisible.value = false
    fetchUsers()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '编辑失败')
  } finally {
    editLoading.value = false
  }
}

async function handleToggleStatus(row: { id: number; status: string }) {
  const newStatus = row.status === 'active' ? 0 : 1
  toggleLoading.value = row.id
  try {
    await userApi.update(row.id, { status: newStatus })
    ElMessage.success(newStatus === 1 ? '已启用' : '已禁用')
    fetchUsers()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '操作失败')
  } finally {
    toggleLoading.value = null
  }
}

async function handleDelete(row: { id: number; name: string }) {
  try {
    await ElMessageBox.confirm(
      `确定要删除教师「${row.name}」吗？删除后数据将无法恢复。`,
      '删除确认',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }

  deleteLoading.value = row.id
  try {
    await userApi.delete(row.id)
    ElMessage.success('教师已删除')
    fetchUsers()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '删除失败')
  } finally {
    deleteLoading.value = null
  }
}

onMounted(() => {
  fetchUsers()
})
</script>