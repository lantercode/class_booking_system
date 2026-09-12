<template>
  <div class="page-container">
    <div class="page-header">
      <h2>课程管理</h2>
      <el-button type="primary" @click="openCourseCreateDialog">
        新增
      </el-button>
    </div>

    <div class="course-layout">
      <!-- 左侧：课程分类 -->
      <div class="category-panel">
        <div class="panel-header">
          <h3>课程类型</h3>
          <el-button type="primary" size="small" text @click="openTypeCreateDialog">
            新增
          </el-button>
        </div>

        <div class="category-list" v-loading="typeLoading">
          <div
            class="category-item"
            :class="{ active: selectedTypeCode === null }"
            @click="selectType(null)"
          >
            <div class="category-icon-wrapper icon-all">
              <el-icon><Folder /></el-icon>
            </div>
            <span class="category-name">全部课程</span>
          </div>

          <div
            v-for="type in courseTypes"
            :key="type.id"
            class="category-item"
            :class="{ active: selectedTypeCode === type.code }"
            @click="selectType(type)"
          >
            <div class="category-icon-wrapper" :class="getCategoryIconClass(type.code)">
              <el-icon><component :is="getCategoryIcon(type.code)" /></el-icon>
            </div>
            <el-tooltip :content="type.name" placement="top">
              <span class="category-name">{{ type.name }}</span>
            </el-tooltip>
            <div class="category-actions" @click.stop>
              <el-button type="primary" size="small" text @click="openTypeEditDialog(type)">
                <el-icon><Edit /></el-icon>
              </el-button>
              <el-button type="danger" size="small" text @click="handleDeleteType(type)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>

          <el-empty v-if="!typeLoading && courseTypes.length === 0" description="暂无课程类型" :image-size="60" />
        </div>

      </div>

      <!-- 右侧：课程列表 -->
      <div class="course-list-panel">
        <div class="filter-bar">
          <el-input
            v-model="search"
            placeholder="请输入课程名称"
            prefix-icon="Search"
            style="width:260px"
            clearable
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          />
          <el-select
            v-model="levelFilter"
            placeholder="难度等级：全部"
            style="width:160px"
            clearable
            @change="handleSearch"
          >
            <el-option label="入门" value="入门" />
            <el-option label="初级" value="初级" />
            <el-option label="中级" value="中级" />
            <el-option label="高级" value="高级" />
          </el-select>
          <el-select
            v-model="statusFilter"
            placeholder="课程状态：全部"
            style="width:160px"
            clearable
            @change="handleSearch"
          >
            <el-option label="上架" :value="1" />
            <el-option label="下架" :value="0" />
          </el-select>
          <el-button @click="handleReset">重置</el-button>
        </div>

        <div class="table-wrapper" v-loading="loading">
          <el-table :data="courses" stripe style="width:100%" :header-cell-style="headerCellStyle">
            <el-table-column type="index" label="序号" width="60" align="center" />
            <el-table-column label="课程名称">
              <template #default="{ row }">
                {{ row.name || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="课程分类">
              <template #default="{ row }">
                <el-tag :type="getCategoryTagType(row.category)" size="small" effect="light" round>
                  {{ row.category || '-' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="难度等级" width="120">
              <template #default="{ row }">
                <div class="level-cell">
                  <div class="stars">
                    <span v-for="i in 5" :key="i" class="star" :class="{ active: i <= getLevelStars(row.level) }">★</span>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="课程状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small" effect="light" round>
                  {{ row.status === 1 ? '上架' : '下架' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <div class="action-cell">
                  <el-button type="primary" size="small" link @click="openCourseEditDialog(row)">编辑</el-button>
                  <el-button
                    :type="row.status === 1 ? 'warning' : 'success'"
                    size="small"
                    link
                    @click="toggleCourseStatus(row)"
                  >{{ row.status === 1 ? '下架' : '上架' }}</el-button>
                  <el-button type="danger" size="small" link @click="handleDeleteCourse(row)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="pagination-wrapper">
          <el-pagination
            background
            layout="total, prev, pager, next"
            :total="total"
            :page-size="pageSize"
            v-model:current-page="currentPage"
            @current-change="fetchCourses"
          />
        </div>
      </div>
    </div>

    <!-- 课程类型对话框 -->
    <el-dialog
      v-model="typeDialogVisible"
      :title="isTypeEdit ? '编辑' : '新增'"
      width="520px"
      :close-on-click-modal="false"
      @close="handleTypeDialogClose"
    >
      <el-form ref="typeFormRef" :model="typeForm" :rules="typeRules" label-width="100px">
        <el-form-item label="类型名称" prop="name">
          <el-input v-model="typeForm.name" placeholder="如：常规课、特色课、私教课" />
        </el-form-item>
        <el-form-item label="类型代码" prop="code">
          <el-input v-model="typeForm.code" placeholder="如：regular、special、private" :disabled="isTypeEdit" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="typeForm.description" type="textarea" :rows="3" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item label="排序" prop="sort_order">
          <el-input-number v-model="typeForm.sort_order" :min="0" style="width:100%" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-radio-group v-model="typeForm.status">
            <el-radio :value="1">启用</el-radio>
            <el-radio :value="0">禁用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="typeDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleTypeSubmit" :loading="typeSubmitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 课程对话框 -->
    <el-dialog
      v-model="courseDialogVisible"
      :title="isCourseEdit ? '编辑' : '新增'"
      width="560px"
      :close-on-click-modal="false"
      @close="handleCourseDialogClose"
    >
      <el-form ref="courseFormRef" :model="courseForm" :rules="courseRules" label-width="100px">
        <el-form-item label="课程名称" prop="name">
          <el-input v-model="courseForm.name" placeholder="请输入课程名称" />
        </el-form-item>
        <el-form-item label="课程类型" prop="course_type_code">
          <el-select v-model="courseForm.course_type_code" placeholder="请选择课程类型" style="width:100%">
            <el-option
              v-for="type in courseTypes"
              :key="type.code"
              :label="type.name"
              :value="type.code"
              :disabled="type.status !== 1"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="课程分类" prop="category">
          <el-select v-model="courseForm.category" placeholder="请选择或输入分类" clearable allow-create style="width:100%">
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
          <el-select v-model="courseForm.level" placeholder="请选择或输入难度" clearable allow-create style="width:100%">
            <el-option label="入门" value="入门" />
            <el-option label="初级" value="初级" />
            <el-option label="中级" value="中级" />
            <el-option label="高级" value="高级" />
          </el-select>
        </el-form-item>
        <el-form-item label="时长(分钟)" prop="duration_minutes">
          <el-input-number v-model="courseForm.duration_minutes" :min="1" :max="480" style="width:100%" />
        </el-form-item>
        <el-form-item label="价格(元)" prop="price">
          <el-input-number v-model="courseForm.price" :min="0" :precision="2" style="width:100%" />
        </el-form-item>
        <el-form-item label="所需积分" prop="required_credits">
          <el-input-number v-model="courseForm.required_credits" :min="0" style="width:100%" />
        </el-form-item>
        <el-form-item label="课程描述" prop="description">
          <el-input v-model="courseForm.description" type="textarea" :rows="3" placeholder="请输入课程描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="courseDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCourseSubmit" :loading="courseSubmitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Plus, Edit, Delete, Folder, User, Medal, Star, Microphone } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  courseApi,
  courseTypeApi,
  type Course,
  type CourseType,
  type CourseCreateParams,
  type CourseUpdateParams,
  type CourseTypeCreateParams,
  type CourseTypeUpdateParams,
} from '@dance-saas/api-client'

// ==================== 课程类型相关 ====================
const typeLoading = ref(false)
const typeSubmitting = ref(false)
const courseTypes = ref<CourseType[]>([])
const selectedTypeCode = ref<string | null>(null)

const typeDialogVisible = ref(false)
const isTypeEdit = ref(false)
const editingTypeId = ref<number | null>(null)
const typeFormRef = ref()

const typeForm = ref<CourseTypeCreateParams>({
  name: '',
  code: '',
  description: '',
  sort_order: 0,
  status: 1,
})

const typeRules = {
  name: [{ required: true, message: '请输入类型名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入类型代码', trigger: 'blur' }],
}

async function fetchCourseTypes() {
  typeLoading.value = true
  try {
    const res = await courseTypeApi.list({ status: undefined })
    const data = res.data as any
    courseTypes.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '加载课程类型失败')
  } finally {
    typeLoading.value = false
  }
}

function selectType(type: CourseType | null) {
  selectedTypeCode.value = type ? type.code : null
  currentPage.value = 1
  fetchCourses()
}

function getTypeName(code: string | null): string {
  if (!code) return '-'
  const type = courseTypes.value.find(t => t.code === code)
  return type ? type.name : code
}

function getCourseCountByType(code: string): number {
  return courses.value.filter(c => c.course_type_code === code).length
}

function getCategoryIcon(code: string) {
  const iconMap: Record<string, any> = {
    children: Microphone,
    adult: User,
    exam: Medal,
    interest: Star,
  }
  return iconMap[code] || Folder
}

function getCategoryIconClass(code: string): string {
  const classMap: Record<string, string> = {
    children: 'icon-children',
    adult: 'icon-adult',
    exam: 'icon-exam',
    interest: 'icon-interest',
  }
  return classMap[code] || 'icon-default'
}

function openTypeCreateDialog() {
  isTypeEdit.value = false
  editingTypeId.value = null
  typeForm.value = {
    name: '',
    code: '',
    description: '',
    sort_order: 0,
    status: 1,
  }
  typeDialogVisible.value = true
}

function openTypeEditDialog(row: CourseType) {
  isTypeEdit.value = true
  editingTypeId.value = row.id
  typeForm.value = {
    name: row.name,
    code: row.code,
    description: row.description || '',
    sort_order: row.sort_order,
    status: row.status,
  }
  typeDialogVisible.value = true
}

function handleTypeDialogClose() {
  typeFormRef.value?.clearValidate()
}

async function handleTypeSubmit() {
  const valid = await typeFormRef.value?.validate().catch(() => false)
  if (!valid) return

  typeSubmitting.value = true
  try {
    if (isTypeEdit.value && editingTypeId.value) {
      await courseTypeApi.update(editingTypeId.value, typeForm.value as CourseTypeUpdateParams)
      ElMessage.success('课程类型更新成功')
    } else {
      await courseTypeApi.create(typeForm.value)
      ElMessage.success('课程类型创建成功')
    }
    typeDialogVisible.value = false
    fetchCourseTypes()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '操作失败')
  } finally {
    typeSubmitting.value = false
  }
}

async function handleDeleteType(row: CourseType) {
  try {
    await ElMessageBox.confirm(`确定要删除课程类型「${row.name}」吗？如有课程使用此类型则无法删除。`, '警告', { type: 'error' })
    await courseTypeApi.remove(row.id)
    ElMessage.success('删除成功')
    if (selectedTypeCode.value === row.code) {
      selectedTypeCode.value = null
    }
    fetchCourseTypes()
    fetchCourses()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.msg || '删除失败')
    }
  }
}

// ==================== 课程相关 ====================
const loading = ref(false)
const courseSubmitting = ref(false)
const courses = ref<Course[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const search = ref('')
const levelFilter = ref('')
const statusFilter = ref<number | null>(null)

const courseDialogVisible = ref(false)
const isCourseEdit = ref(false)
const editingCourseId = ref<number | null>(null)
const courseFormRef = ref()

const courseForm = ref<CourseCreateParams>({
  name: '',
  course_type_code: '',
  category: undefined,
  level: undefined,
  duration_minutes: 60,
  price: 0,
  required_credits: 1,
  description: '',
})

const courseRules = computed(() => ({
  name: [{ required: true, message: '请输入课程名称', trigger: 'blur' }],
  course_type_code: [{ required: true, message: '请选择课程类型', trigger: 'change' }],
  category: [{ required: true, message: '请选择分类', trigger: 'blur' }],
  level: [{ required: true, message: '请选择难度等级', trigger: 'blur' }],
  duration_minutes: [{ required: true, message: '请输入时长', trigger: 'blur' }],
}))

async function fetchCourses() {
  loading.value = true
  try {
    const res = await courseApi.list({
      page: currentPage.value,
      page_size: pageSize.value,
      keyword: search.value || undefined,
      level: levelFilter.value || undefined,
      status: statusFilter.value !== null ? statusFilter.value : undefined,
      course_type_code: selectedTypeCode.value || undefined,
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

function handleReset() {
  search.value = ''
  levelFilter.value = ''
  statusFilter.value = null
  selectedTypeCode.value = null
  currentPage.value = 1
  fetchCourses()
}

function handlePageSizeChange() {
  currentPage.value = 1
  fetchCourses()
}

function getLevelStars(level: string | undefined): number {
  const map: Record<string, number> = {
    '入门': 1,
    '初级': 2,
    '中级': 3,
    '高级': 4,
  }
  return map[level || ''] || 0
}

function getCategoryTagType(category: string | undefined): string {
  const map: Record<string, string> = {
    '少儿舞蹈': 'danger',
    '成人舞蹈': 'primary',
    '考级课程': 'warning',
    '兴趣课程': 'success',
    '爵士舞': 'danger',
    '街舞': 'primary',
    '中国舞': 'warning',
    '芭蕾': 'success',
    '拉丁': 'danger',
    '现代舞': 'primary',
    '瑜伽': 'success',
  }
  return map[category || ''] || 'info'
}

function getCourseThumbColor(row: Course): string {
  const colors = [
    'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
    'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
    'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
    'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
    'linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%)',
    'linear-gradient(135deg, #fccb90 0%, #d57eeb 100%)',
  ]
  const index = (row.id || 0) % colors.length
  return colors[index]
}

function getCourseThumbText(row: Course): string {
  const name = row.name || ''
  if (name.includes('芭蕾')) return '🩰'
  if (name.includes('街舞')) return ''
  if (name.includes('拉丁')) return '💃'
  if (name.includes('中国舞')) return '🎭'
  if (name.includes('爵士')) return ''
  if (name.includes('现代')) return '🌟'
  if (name.includes('瑜伽')) return '🧘'
  if (name.includes('形体')) return '✨'
  return '🎨'
}

const headerCellStyle = {
  background: '#f8f9fb',
  color: '#606266',
  fontWeight: '500',
  fontSize: '14px',
}

function openCourseCreateDialog() {
  isCourseEdit.value = false
  editingCourseId.value = null
  courseForm.value = {
    name: '',
    course_type_code: selectedTypeCode.value || '',
    category: undefined,
    level: undefined,
    duration_minutes: 60,
    price: 0,
    required_credits: 1,
    description: '',
  }
  courseDialogVisible.value = true
}

function openCourseEditDialog(row: Course) {
  isCourseEdit.value = true
  editingCourseId.value = row.id
  courseForm.value = {
    name: row.name,
    course_type_code: row.course_type_code || '',
    category: row.category || undefined,
    level: row.level || undefined,
    duration_minutes: row.duration_minutes,
    price: row.price,
    required_credits: row.required_credits,
    description: row.description || '',
  }
  courseDialogVisible.value = true
}

function handleCourseDialogClose() {
  courseFormRef.value?.clearValidate()
}

async function handleCourseSubmit() {
  const valid = await courseFormRef.value?.validate().catch(() => false)
  if (!valid) return

  courseSubmitting.value = true
  try {
    if (isCourseEdit.value && editingCourseId.value) {
      await courseApi.update(editingCourseId.value, courseForm.value as CourseUpdateParams)
      ElMessage.success('课程更新成功')
    } else {
      await courseApi.create(courseForm.value)
      ElMessage.success('课程创建成功')
    }
    courseDialogVisible.value = false
    fetchCourses()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '操作失败')
  } finally {
    courseSubmitting.value = false
  }
}

async function toggleCourseStatus(row: Course) {
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

async function handleDeleteCourse(row: Course) {
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
  fetchCourseTypes()
  fetchCourses()
})
</script>

<style scoped>
.course-layout {
  display: flex;
  gap: 20px;
  margin-top: 16px;
  align-items: stretch;
  flex: 1;
  min-height: 0;
}

/* ===== 左侧分类面板 ===== */
.category-panel {
  width: 260px;
  flex-shrink: 0;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #ebeef5;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}

.panel-header h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.category-list {
  padding: 8px;
  flex: 1;
  overflow-y: auto;
}

.category-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  margin-bottom: 4px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.category-item:hover {
  background: #f5f7fa;
}

.category-item.active {
  background: #ecf5ff;
}

.category-item.active .category-name {
  color: #409eff;
  font-weight: 600;
}

.category-item.active .category-icon-wrapper {
  background: #409eff;
  color: #fff;
}

.category-icon-wrapper {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
  transition: all 0.2s;
}

.icon-all {
  background: #f0f5ff;
  color: #409eff;
}

.icon-children {
  background: #fff0f0;
  color: #f56c6c;
}

.icon-adult {
  background: #f0f5ff;
  color: #409eff;
}

.icon-exam {
  background: #fdf6ec;
  color: #e6a23c;
}

.icon-interest {
  background: #f0f9eb;
  color: #67c23a;
}

.category-name {
  flex: 1;
  font-size: 14px;
  color: #606266;
  transition: all 0.2s;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.category-count {
  font-size: 12px;
  color: #909399;
  background: #f5f7fa;
  padding: 2px 8px;
  border-radius: 10px;
  min-width: 24px;
  text-align: center;
}

.category-item.active .category-count {
  background: #409eff;
  color: #fff;
}

.category-actions {
  opacity: 0;
  transition: opacity 0.2s;
  display: flex;
  gap: 0;
  margin-left: auto;
}

.category-item:hover .category-actions {
  opacity: 1;
}

/* 底部装饰 */
.category-footer {
  margin: 12px;
  padding: 16px;
  background: linear-gradient(135deg, #f5f0ff 0%, #e8f4fd 100%);
  border-radius: 10px;
  text-align: center;
  flex-shrink: 0;
}

.footer-text p {
  margin: 0;
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}

.footer-text p:first-child {
  font-weight: 600;
  color: #409eff;
}

.footer-tags {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}

/* ===== 右侧课程列表 ===== */
.course-list-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
  flex-shrink: 0;
}

.table-wrapper {
  flex: 1;
  min-height: 0;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #ebeef5;
  overflow: hidden;
  display: flex;
  flex-direction: column;

  :deep(.el-table) {
    flex: 1;
  }
}

/* 课程单元格 */
.course-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}

.course-thumb {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.thumb-text {
  font-size: 24px;
}

.course-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.course-name {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 难度星级 */
.level-cell {
  display: flex;
  align-items: center;
}

.stars {
  display: flex;
  gap: 2px;
}

.star {
  font-size: 14px;
  color: #e4e7ed;
}

.star.active {
  color: #f5a623;
}

/* 操作列 */
.action-cell {
  display: flex;
  gap: 4px;
}
</style>