<template>
  <div class="page-container">
    <div class="page-header">
      <h2>课程管理</h2>
      <el-button type="primary" @click="openCreateDialog">
        <el-icon><Plus /></el-icon>新增课程
      </el-button>
    </div>

    <div style="display:flex;gap:12px;margin-bottom:16px">
      <el-input v-model="search" placeholder="搜索课程名称" style="width:240px" clearable @keyup.enter="handleSearch" @clear="handleSearch" />
      <el-select v-model="levelFilter" placeholder="请选择或输入难度" style="width:140px" clearable allow-create @change="handleSearch">
        <el-option label="入门" value="入门" />
        <el-option label="初级" value="初级" />
        <el-option label="中级" value="中级" />
        <el-option label="高级" value="高级" />
      </el-select>
      <el-select v-model="categoryFilter" placeholder="请选择或输入分类" style="width:140px" clearable allow-create @change="handleSearch">
        <el-option label="爵士舞" value="爵士舞" />
        <el-option label="街舞" value="街舞" />
        <el-option label="中国舞" value="中国舞" />
        <el-option label="芭蕾" value="芭蕾" />
        <el-option label="拉丁" value="拉丁" />
        <el-option label="现代舞" value="现代舞" />
        <el-option label="瑜伽" value="瑜伽" />
      </el-select>
    </div>

    <el-table :data="courses" stripe style="width:100%" v-loading="loading">
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="name" label="课程名称" min-width="140" />
      <el-table-column prop="category" label="分类" width="100" />
      <el-table-column prop="level" label="难度" width="80">
        <template #default="{ row }">
          <el-tag
            :type="row.level === '入门' ? 'success' : row.level === '初级' ? 'info' : row.level === '高级' ? 'danger' : 'warning'"
            size="small"
          >{{ row.level || '-' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="duration_minutes" label="时长(分)" width="90" />
      <el-table-column prop="max_capacity" label="容量" width="70" />
      <el-table-column prop="price" label="价格(元)" width="90" />
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
            {{ row.status === 1 ? '上架' : '下架' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" link @click="openEditDialog(row)">编辑</el-button>
          <el-button
            :type="row.status === 1 ? 'warning' : 'success'"
            size="small"
            link
            @click="toggleStatus(row)"
          >{{ row.status === 1 ? '下架' : '上架' }}</el-button>
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
        v-model:current-page="currentPage"
        @current-change="fetchCourses"
      />
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑课程' : '新增课程'"
      width="560px"
      :close-on-click-modal="false"
      @close="handleDialogClose"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="课程名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入课程名称" />
        </el-form-item>
        <el-form-item label="分类" prop="category">
          <el-select v-model="form.category" placeholder="请选择或输入分类" clearable allow-create style="width:100%">
            <el-option label="爵士舞" value="爵士舞" />
            <el-option label="街舞" value="街舞" />
            <el-option label="中国舞" value="中国舞" />
            <el-option label="芭蕾" value="芭蕾" />
            <el-option label="拉丁" value="拉丁" />
            <el-option label="现代舞" value="现代舞" />
            <el-option label="瑜伽" value="瑜伽" />
          </el-select>
        </el-form-item>
        <el-form-item label="难度等级" prop="level">
          <el-select v-model="form.level" placeholder="请选择或输入难度" clearable allow-create style="width:100%">
            <el-option label="入门" value="入门" />
            <el-option label="初级" value="初级" />
            <el-option label="中级" value="中级" />
            <el-option label="高级" value="高级" />
          </el-select>
        </el-form-item>
        <el-form-item label="时长(分钟)" prop="duration_minutes">
          <el-input-number v-model="form.duration_minutes" :min="1" :max="480" style="width:100%" />
        </el-form-item>
        <el-form-item label="价格(元)" prop="price">
          <el-input-number v-model="form.price" :min="0" :precision="2" style="width:100%" />
        </el-form-item>
        <el-form-item label="所需积分" prop="required_credits">
          <el-input-number v-model="form.required_credits" :min="0" style="width:100%" />
        </el-form-item>
        <el-form-item label="课程描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请输入课程描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { courseApi, type Course, type CourseCreateParams, type CourseUpdateParams } from '@dance-saas/api-client'

const loading = ref(false)
const submitting = ref(false)
const courses = ref<Course[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const search = ref('')
const levelFilter = ref('')
const categoryFilter = ref('')

const dialogVisible = ref(false)
const isEdit = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref()

const form = ref<CourseCreateParams>({
  name: '',
  category: undefined,
  level: undefined,
  duration_minutes: 60,
  price: 0,
  required_credits: 1,
  description: '',
})

const rules = {
  name: [{ required: true, message: '请输入课程名称', trigger: 'blur' }],
  category: [{ required: true, message: '请选择分类', trigger: 'blur' }],
  level: [{ required: true, message: '请选择难度等级', trigger: 'blur' }],
  duration_minutes: [{ required: true, message: '请输入时长', trigger: 'blur' }],
}

async function fetchCourses() {
  loading.value = true
  try {
    const res = await courseApi.list({
      page: currentPage.value,
      page_size: pageSize.value,
      keyword: search.value || undefined,
      level: levelFilter.value || undefined,
      category: categoryFilter.value || undefined,
    })
    courses.value = res.data.items
    total.value = res.data.total
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '加载课程列表失败')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  currentPage.value = 1
  fetchCourses()
}

function openCreateDialog() {
  isEdit.value = false
  editingId.value = null
  form.value = {
    name: '',
    category: undefined,
    level: undefined,
    duration_minutes: 60,
    max_capacity: 20,
    price: 0,
    required_credits: 1,
    description: '',
  }
  dialogVisible.value = true
}

function openEditDialog(row: Course) {
  isEdit.value = true
  editingId.value = row.id
  form.value = {
    name: row.name,
    category: row.category || undefined,
    level: row.level || undefined,
    duration_minutes: row.duration_minutes,
    max_capacity: row.max_capacity,
    price: row.price,
    required_credits: row.required_credits,
    description: row.description || '',
  }
  dialogVisible.value = true
}

function handleDialogClose() {
  formRef.value?.clearValidate()
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (isEdit.value && editingId.value) {
      await courseApi.update(editingId.value, form.value as CourseUpdateParams)
      ElMessage.success('课程更新成功')
    } else {
      await courseApi.create(form.value)
      ElMessage.success('课程创建成功')
    }
    dialogVisible.value = false
    fetchCourses()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function toggleStatus(row: Course) {
  const newStatus = row.status === 1 ? 0 : 1
  const action = newStatus === 0 ? '下架' : '上架'
  try {
    await ElMessageBox.confirm(`确定要${action}课程「${row.name}」吗？`, '提示', { type: 'warning' })
    await courseApi.update(row.id, { status: newStatus })
    ElMessage.success(`${action}成功`)
    fetchCourses()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.msg || '操作失败')
    }
  }
}

async function handleDelete(row: Course) {
  try {
    await ElMessageBox.confirm(`确定要删除课程「${row.name}」吗？此操作不可恢复。`, '警告', { type: 'error' })
    await courseApi.remove(row.id)
    ElMessage.success('删除成功')
    fetchCourses()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.msg || '删除失败')
    }
  }
}

onMounted(() => {
  fetchCourses()
})
</script>