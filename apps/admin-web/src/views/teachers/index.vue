<template>
  <div class="page-container">
    <div class="page-header">
      <h2>教师管理</h2>
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

    <el-table v-loading="loading" :data="filteredTeachers" stripe style="width: 100%">
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column label="头像" width="80" align="center">
        <template #default="{ row }">
          <el-avatar :size="40" :src="row.avatar_url">
            {{ row.name?.charAt(0) || '教' }}
          </el-avatar>
        </template>
      </el-table-column>
      <el-table-column prop="teacher_code" label="教师编号" width="160">
        <template #default="{ row }">
          <el-link type="primary" @click="handleDetail(row)">
            {{ row.teacher_code || '--' }}
          </el-link>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="姓名" />
      <el-table-column prop="phone" label="手机号" width="140" />
      <el-table-column prop="status" label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'danger'" size="small">
            {{ row.status === 'active' ? '正常' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="joinedAt" label="加入时间" width="120" />
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
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrapper">
      <el-pagination
        v-model:current-page="page"
        background
        layout="total, prev, pager, next"
        :total="filteredTeachers.length"
        :page-size="20"
      />
    </div>

    <el-dialog v-model="dialogVisible" title="编辑" width="560px" :close-on-click-modal="false">
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px">
        <el-form-item label="手机号">
          <el-input :model-value="form.phone" disabled />
        </el-form-item>
        <el-form-item label="昵称" prop="nickname">
          <el-input v-model="form.nickname" placeholder="请输入昵称" maxlength="20" />
        </el-form-item>
        <el-form-item label="头像" prop="avatar_url">
          <el-upload
            class="avatar-uploader"
            :show-file-list="false"
            :before-upload="beforeAvatarUpload"
            :http-request="handleAvatarUpload"
          >
            <img v-if="form.avatar_url" :src="form.avatar_url" class="avatar-image" />
            <el-icon v-else class="avatar-uploader-icon"><Plus /></el-icon>
          </el-upload>
          <div class="upload-tip">支持 JPG/PNG 格式，文件大小不超过 2MB，建议尺寸 200x200 像素</div>
        </el-form-item>
        <el-form-item label="教师简介">
          <el-input
            v-model="form.bio"
            type="textarea"
            :rows="8"
            placeholder="请输入教师简介/简历内容，例如：&#10;• 舞龄：X年&#10;• 教学经验：X年&#10;• 就读学校：XXX大学舞蹈专业&#10;• 获得奖励：XXX舞蹈比赛金奖&#10;• 擅长舞种：中国舞、古典舞、民族民间舞"
          />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="form.status" style="width: 100%">
            <el-option label="正常" :value="1" />
            <el-option label="禁用" :value="0" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false"> 取消 </el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit"> 确定 </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailVisible" title="教师详情" width="560px" :close-on-click-modal="false">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="教师编号">
          {{ detailData.teacher_code || '--' }}
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
        <el-descriptions-item label="教师简介">
          {{ detailData.bio || '--' }}
        </el-descriptions-item>
        <el-descriptions-item label="加入时间">
          {{ detailData.joinedAt || '--' }}
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="detailVisible = false"> 关闭 </el-button>
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
const page = ref(1)
const loading = ref(false)
const submitLoading = ref(false)
const toggleLoading = ref<number | null>(null)
const deleteLoading = ref<number | null>(null)
const users = ref<User[]>([])

const dialogVisible = ref(false)
const detailVisible = ref(false)
const formRef = ref<FormInstance>()
const editId = ref(0)

const detailData = ref({
  id: 0,
  teacher_code: '',
  name: '',
  phone: '',
  status: '' as string,
  joinedAt: '',
  avatar_url: '',
  bio: '',
})

const form = ref({
  phone: '',
  nickname: '',
  avatar_url: '',
  bio: '',
  status: 1 as number,
})

const formRules: FormRules = {
  nickname: [{ required: true, message: '请输入昵称', trigger: 'blur' }],
}

const teachers = computed(() => {
  return users.value.filter(u => u.roles.includes('teacher'))
})

const filteredTeachers = computed(() => {
  return teachers.value
    .filter(t => {
      const name = t.nickname || t.phone
      if (search.value && !name.includes(search.value) && !t.phone.includes(search.value))
        return false
      if (statusFilter.value === 'active' && t.status !== 1) return false
      if (statusFilter.value === 'disabled' && t.status !== 0) return false
      return true
    })
    .map(t => ({
      id: t.id,
      teacher_code: t.teacher_code || '',
      name: t.nickname || t.phone,
      phone: t.phone,
      status: t.status === 1 ? ('active' as const) : ('disabled' as const),
      joinedAt: t.created_at?.slice(0, 10) || '',
      avatar_url: t.avatar_url || '',
      bio: t.bio || '',
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

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitLoading.value = true
  try {
    await userApi.update(editId.value, {
      nickname: form.value.nickname || undefined,
      avatar_url: form.value.avatar_url || undefined,
      bio: form.value.bio || undefined,
      status: form.value.status,
    })
    ElMessage.success('编辑成功')
    dialogVisible.value = false
    fetchUsers()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '编辑失败')
  } finally {
    submitLoading.value = false
  }
}

function handleEdit(row: {
  id: number
  phone: string
  name: string
  status: string
  avatar_url?: string
  bio?: string
}) {
  editId.value = row.id
  form.value = {
    phone: row.phone,
    nickname: row.name,
    avatar_url: row.avatar_url || '',
    bio: row.bio || '',
    status: row.status === 'active' ? 1 : 0,
  }
  formRef.value?.resetFields()
  dialogVisible.value = true
  formRef.value?.clearValidate()
}

function handleDetail(row: {
  id: number
  teacher_code: string
  name: string
  phone: string
  status: string
  joinedAt: string
  avatar_url?: string
  bio?: string
}) {
  detailData.value = {
    id: row.id,
    teacher_code: row.teacher_code || '',
    name: row.name,
    phone: row.phone,
    status: row.status,
    joinedAt: row.joinedAt,
    avatar_url: row.avatar_url || '',
    bio: row.bio || '',
  }
  detailVisible.value = true
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
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
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
      form.value.avatar_url = result.data.url
      ElMessage.success('头像上传成功')
      formRef.value?.validateField('avatar_url')
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

.avatar-uploader {
  border: 1px dashed #d9d9d9;
  border-radius: 6px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: all 0.3s;
  width: 120px;
  height: 120px;
}

.avatar-uploader:hover {
  border-color: #409eff;
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
  display: block;
  object-fit: cover;
}

.upload-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
  line-height: 1.5;
}
</style>