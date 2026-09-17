<template>
  <div class="page-container">
    <div class="page-header">
      <h2>学员管理</h2>
    </div>

    <div style="display: flex; gap: 12px; margin-bottom: 16px">
      <el-input
        v-model="search"
        placeholder="搜索姓名/手机号"
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

    <el-table v-loading="loading" :data="tableData" stripe style="width: 100%">
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column label="头像" width="80" align="center">
        <template #default="{ row }">
          <el-avatar :size="40" :src="row.avatar_url">
            {{ row.name?.charAt(0) || '学' }}
          </el-avatar>
        </template>
      </el-table-column>
      <el-table-column prop="student_code" label="学员编号" width="160">
        <template #default="{ row }">
          <el-link type="primary" @click="handleDetail(row)">
            {{ row.student_code || '--' }}
          </el-link>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="姓名" />
      <el-table-column prop="phone" label="手机号" width="140" />
      <el-table-column prop="joinedAt" label="加入时间" width="120" />
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'danger'" size="small">
            {{ row.status === 'active' ? '正常' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button type="warning" size="small" link @click="handleEdit(row)"> 编辑 </el-button>
          <el-button
            v-if="row.status === 'active'"
            type="danger"
            size="small"
            link
            :loading="toggleLoading === row.id"
            @click="handleToggleStatus(row)"
          >
            禁用
          </el-button>
          <el-button
            v-else
            type="success"
            size="small"
            link
            :loading="toggleLoading === row.id"
            @click="handleToggleStatus(row)"
          >
            启用
          </el-button>
          <el-button
            v-if="row.status !== 'active'"
            type="danger"
            size="small"
            link
            :loading="deleteLoading === row.id"
            @click="handleDelete(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrapper">
      <el-pagination
        v-model:current-page="page"
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        @current-change="fetchUsers"
      />
    </div>

    <el-dialog v-model="detailVisible" title="学员详情" width="480px" :close-on-click-modal="false">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="学员编号">
          {{ detailData.student_code || '--' }}
        </el-descriptions-item>
        <el-descriptions-item label="头像">
          <el-avatar v-if="detailData.avatar_url" :size="80" :src="detailData.avatar_url" />
          <span v-else style="color: #909399">未上传</span>
        </el-descriptions-item>
        <el-descriptions-item label="姓名">
          {{ detailData.name || '--' }}
        </el-descriptions-item>
        <el-descriptions-item label="手机号">
          {{ detailData.phone || '--' }}
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="detailData.status === 'active' ? 'success' : 'danger'" size="small">
            {{ detailData.status === 'active' ? '正常' : '禁用' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="加入时间">
          {{ detailData.joinedAt || '--' }}
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="detailVisible = false"> 关闭 </el-button>
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
        <el-form-item label="头像" prop="avatar_url">
          <el-upload
            class="avatar-uploader"
            :show-file-list="false"
            :before-upload="beforeAvatarUpload"
            :http-request="handleAvatarUpload"
          >
            <img v-if="editForm.avatar_url" :src="editForm.avatar_url" class="avatar-image" />
            <el-icon v-else class="avatar-uploader-icon"><Plus /></el-icon>
          </el-upload>
          <div class="upload-tip">支持 JPG/PNG 格式，文件大小不超过 2MB，建议尺寸 200x200 像素</div>
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="editForm.status" style="width: 100%">
            <el-option label="正常" :value="1" />
            <el-option label="禁用" :value="0" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false"> 取消 </el-button>
        <el-button type="primary" :loading="editLoading" @click="handleEditSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { commonApi, userApi, type User } from '@dance-saas/api-client'
import { Plus, Search } from '@element-plus/icons-vue'
import type { FormInstance, FormRules, UploadProps } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

const search = ref('')
const statusFilter = ref('')
const loading = ref(false)
const editLoading = ref(false)
const toggleLoading = ref<number | null>(null)
const deleteLoading = ref<number | null>(null)
const users = ref<User[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)

const detailVisible = ref(false)
const editVisible = ref(false)
const editFormRef = ref<FormInstance>()
const editId = ref(0)

const detailData = ref({
  id: 0,
  student_code: '',
  name: '',
  phone: '',
  status: '' as string,
  joinedAt: '',
  avatar_url: '',
})

const editForm = ref({
  phone: '',
  nickname: '',
  avatar_url: '',
  status: 1 as number,
})

const editRules: FormRules = {
  nickname: [{ required: true, message: '请输入昵称', trigger: 'blur' }],
}

const tableData = computed(() => {
  return users.value.map(s => ({
    id: s.id,
    student_code: s.student_code || '',
    name: s.nickname || s.phone,
    phone: s.phone,
    status: s.status === 1 ? ('active' as const) : ('disabled' as const),
    joinedAt: s.created_at?.slice(0, 10) || '',
    avatar_url: s.avatar_url || '',
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

function handleDetail(row: {
  id: number
  student_code: string
  name: string
  phone: string
  status: string
  joinedAt: string
  avatar_url?: string
}) {
  detailData.value = {
    id: row.id,
    student_code: row.student_code || '',
    name: row.name,
    phone: row.phone,
    status: row.status,
    joinedAt: row.joinedAt,
    avatar_url: row.avatar_url || '',
  }
  detailVisible.value = true
}

function handleEdit(row: {
  id: number
  phone: string
  name: string
  status: string
  avatar_url?: string
}) {
  editId.value = row.id
  editForm.value = {
    phone: row.phone,
    nickname: row.name,
    avatar_url: row.avatar_url || '',
    status: row.status === 'active' ? 1 : 0,
  }
  editFormRef.value?.resetFields()
  editVisible.value = true
  editFormRef.value?.clearValidate()
}

async function handleEditSubmit() {
  const valid = await editFormRef.value?.validate().catch(() => false)
  if (!valid) return

  editLoading.value = true
  try {
    await userApi.update(editId.value, {
      nickname: editForm.value.nickname || undefined,
      avatar_url: editForm.value.avatar_url || undefined,
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
      `确定要删除学员「${row.name}」吗？删除后数据将无法恢复！`,
      '删除确认',
      { type: 'warning' }
    )
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

// 头像上传相关函数
const beforeAvatarUpload: UploadProps['beforeUpload'] = file => {
  const allowedTypes = ['image/jpeg', 'image/png']
  const isAllowedType = allowedTypes.includes(file.type)
  const isLt2M = file.size / 1024 / 1024 < 2

  if (!isAllowedType) {
    ElMessage.error('上传头像图片只能是 JPG/PNG 格式!')
    return false
  }
  if (!isLt2M) {
    ElMessage.error('上传头像图片大小不能超过 2MB!')
    return false
  }
  return true
}

const handleAvatarUpload = async (options: any) => {
  const { file } = options

  try {
    const result = await commonApi.uploadImage(file)

    if (result.code === 0 || result.code === 200) {
      editForm.value.avatar_url = result.data.url
      ElMessage.success('头像上传成功')
      editFormRef.value?.validateField('avatar_url')
    } else {
      ElMessage.error(result.msg || '上传失败')
    }
  } catch (error: any) {
    console.error('上传失败:', error)
    const errorMsg = error?.response?.data?.msg || error?.message || '上传失败，请重试'
    ElMessage.error(errorMsg)
  }
}

onMounted(() => {
  fetchUsers()
})
</script>

<style scoped>
.search-icon:hover {
  color: #409eff;
}

.avatar-uploader :deep(.el-upload) {
  border: 1px dashed var(--el-border-color);
  border-radius: 6px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: var(--el-transition-duration-fast);
}

.avatar-uploader :deep(.el-upload:hover) {
  border-color: var(--el-color-primary);
}

.avatar-uploader-icon {
  font-size: 28px;
  color: #8c939d;
  width: 120px;
  height: 120px;
  text-align: center;
  line-height: 120px;
}

.avatar-image {
  width: 120px;
  height: 120px;
  object-fit: cover;
}

.upload-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
  line-height: 1.5;
}
</style>