<template>
  <div class="page-container">
    <div class="page-header">
      <h2>学员管理</h2>
      <el-button type="primary" @click="openCreateDialog"><el-icon><Plus /></el-icon>新增学员</el-button>
    </div>

    <div style="display:flex;gap:12px;margin-bottom:16px">
      <el-input v-model="search" placeholder="搜索姓名/手机号" style="width:240px" clearable @keyup.enter="handleSearch" @clear="handleSearch" />
      <el-select v-model="statusFilter" placeholder="状态筛选" style="width:140px" clearable @change="handleSearch">
        <el-option label="全部" value="" />
        <el-option label="正常" value="active" />
        <el-option label="禁用" value="disabled" />
      </el-select>
    </div>

    <el-table :data="tableData" stripe v-loading="loading" style="width:100%">
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="name" label="姓名" />
      <el-table-column prop="phone" label="手机号" width="140" />
      <el-table-column prop="joinedAt" label="加入时间" width="120" />
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'danger'" size="small">{{ row.status === 'active' ? '正常' : '禁用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" link @click="handleDetail(row)">详情</el-button>
          <el-button type="warning" size="small" link @click="handleEdit(row)">编辑</el-button>
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
            v-if="row.status !== 'active'"
            type="danger"
            size="small"
            link
            :loading="deleteLoading === row.id"
            @click="handleDelete(row)"
          >删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div style="display:flex;justify-content:center;margin-top:20px">
      <el-pagination background layout="total, prev, pager, next" :total="total" :page-size="pageSize" v-model:current-page="page" @current-change="fetchUsers" />
    </div>

    <el-dialog v-model="createVisible" title="新增学员" width="480px" :close-on-click-modal="false">
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

    <el-dialog v-model="detailVisible" title="学员详情" width="480px" :close-on-click-modal="false">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="ID">{{ detailData.id }}</el-descriptions-item>
        <el-descriptions-item label="姓名">{{ detailData.name }}</el-descriptions-item>
        <el-descriptions-item label="手机号">{{ detailData.phone }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="detailData.status === 'active' ? 'success' : 'danger'" size="small">{{ detailData.status === 'active' ? '正常' : '禁用' }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="加入时间">{{ detailData.joinedAt }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editVisible" title="编辑学员" width="480px" :close-on-click-modal="false">
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
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)

const createVisible = ref(false)
const detailVisible = ref(false)
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

const detailData = ref({
  id: 0,
  name: '',
  phone: '',
  status: '' as string,
  joinedAt: '',
})

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

const tableData = computed(() => {
  return users.value.map(s => ({
    id: s.id,
    name: s.nickname || s.phone,
    phone: s.phone,
    status: s.status === 1 ? ('active' as const) : ('disabled' as const),
    joinedAt: s.created_at?.slice(0, 10) || '',
    _raw: s,
  }))
})

async function fetchUsers() {
  loading.value = true
  try {
    const res = await userApi.list({
      page: page.value,
      page_size: pageSize.value,
      role_code: 'student',
      keyword: search.value || undefined,
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

function handleSearch() {
  page.value = 1
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
      role_codes: ['student'],
    })
    ElMessage.success('新增学员成功')
    createVisible.value = false
    fetchUsers()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '新增学员失败')
  } finally {
    createLoading.value = false
  }
}

function handleDetail(row: { id: number; name: string; phone: string; status: string; joinedAt: string }) {
  detailData.value = {
    id: row.id,
    name: row.name,
    phone: row.phone,
    status: row.status,
    joinedAt: row.joinedAt,
  }
  detailVisible.value = true
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
    await ElMessageBox.confirm(`确定要删除学员「${row.name}」吗？删除后数据将无法恢复！`, '删除确认', { type: 'warning' })
    deleteLoading.value = row.id
    await userApi.delete(row.id)
    ElMessage.success('学员已删除')
    fetchUsers()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.msg || '删除失败')
    }
  } finally {
    deleteLoading.value = null
  }
}

onMounted(() => {
  fetchUsers()
})
</script>