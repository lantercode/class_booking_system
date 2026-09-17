<template>
  <div class="page-container">
    <div class="page-header">
      <h2>课程管理</h2>
    </div>

    <div class="course-layout">
      <!-- 左侧：舞蹈分类 -->
      <div class="category-panel">
        <div class="panel-tabs-header">
          <el-tabs v-model="categoryTab" class="category-tabs" @tab-click="onCategoryTabChange">
            <el-tab-pane label="课程类型" name="type" />
            <el-tab-pane label="舞蹈分类" name="category" />
          </el-tabs>
          <el-button type="primary" size="small" text @click="handleAddClick"> 新增 </el-button>
        </div>

        <!-- 课程类型列表 -->
        <div v-show="categoryTab === 'type'" class="panel-content">
          <div v-loading="typeLoading" class="category-list">
            <div
              class="category-item"
              :class="{ active: selectedTypeCode === null }"
              @click="selectType(null)"
            >
              <div class="category-icon-wrapper icon-all">
                <el-icon><Folder /></el-icon>
              </div>
              <span class="category-name">全部</span>
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

            <el-empty
              v-if="!typeLoading && courseTypes.length === 0"
              description="--"
              :image-size="60"
            />
          </div>
        </div>

        <!-- 舞蹈分类列表 -->
        <div v-show="categoryTab === 'category'" class="panel-content">
          <div v-loading="categoryLoading" class="category-list">
            <div
              class="category-item"
              :class="{ active: selectedCategoryCode === null }"
              @click="selectCategory(null)"
            >
              <div class="category-icon-wrapper icon-all">
                <el-icon><Folder /></el-icon>
              </div>
              <span class="category-name">全部</span>
            </div>

            <div
              v-for="cat in courseCategories"
              :key="cat.id"
              class="category-item"
              :class="{ active: selectedCategoryCode === cat.code }"
              @click="selectCategory(cat)"
            >
              <div class="category-icon-wrapper icon-category">
                <el-icon><Star /></el-icon>
              </div>
              <el-tooltip :content="cat.name" placement="top">
                <span class="category-name">{{ cat.name }}</span>
              </el-tooltip>
              <div class="category-actions" @click.stop>
                <el-button type="primary" size="small" text @click="openCategoryEditDialog(cat)">
                  <el-icon><Edit /></el-icon>
                </el-button>
                <el-button type="danger" size="small" text @click="handleDeleteCategory(cat)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>

            <el-empty
              v-if="!categoryLoading && courseCategories.length === 0"
              description="--"
              :image-size="60"
            />
          </div>
        </div>
      </div>

      <!-- 右侧：课程列表 -->
      <div class="course-list-panel">
        <!-- 当前筛选条件提示 -->
        <div v-if="selectedTypeCode || selectedCategoryCode" class="active-filters">
          <span class="filter-label">当前筛选：</span>
          <el-tag
            v-if="selectedTypeCode"
            closable
            type="primary"
            size="small"
            effect="light"
            @close="selectType(null)"
          >
            课程类型：{{ getTypeName(selectedTypeCode) }}
          </el-tag>
          <el-tag
            v-if="selectedCategoryCode"
            closable
            type="success"
            size="small"
            effect="light"
            @close="selectCategory(null)"
          >
            舞蹈分类：{{ getCategoryName(selectedCategoryCode) }}
          </el-tag>
          <el-button type="primary" link size="small" @click="clearAllFilters">
            清除全部
          </el-button>
        </div>

        <div class="filter-bar">
          <el-input
            v-model="search"
            placeholder="请输入课程名称"
            style="width: 260px"
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
            v-model="levelFilter"
            placeholder="难度等级：全部"
            style="width: 160px"
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
            style="width: 160px"
            clearable
            @change="handleSearch"
          >
            <el-option label="上架" :value="1" />
            <el-option label="下架" :value="0" />
          </el-select>
          <div class="filter-bar-actions">
            <el-button type="primary" @click="openCourseCreateDialog"> 新增 </el-button>
          </div>
        </div>

        <div v-loading="loading" class="table-wrapper">
          <el-table :data="courses" stripe style="width: 100%" :header-cell-style="headerCellStyle">
            <el-table-column type="index" label="序号" width="60" align="center" />
            <el-table-column label="课程名称">
              <template #default="{ row }">
                {{ row.name || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="难度等级" width="120">
              <template #default="{ row }">
                <div class="level-cell">
                  <div class="stars">
                    <span
                      v-for="i in 5"
                      :key="i"
                      class="star"
                      :class="{ active: i <= getLevelStars(row.level) }"
                      >★</span
                    >
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="课程状态" width="100">
              <template #default="{ row }">
                <el-tag
                  :type="row.status === 1 ? 'success' : 'info'"
                  size="small"
                  effect="light"
                  round
                >
                  {{ row.status === 1 ? '上架' : '下架' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <div class="action-cell">
                  <el-button type="primary" size="small" link @click="openCourseEditDialog(row)">
                    编辑
                  </el-button>
                  <el-button
                    :type="row.status === 1 ? 'warning' : 'success'"
                    size="small"
                    link
                    @click="toggleCourseStatus(row)"
                  >
                    {{ row.status === 1 ? '下架' : '上架' }}
                  </el-button>
                  <el-button type="danger" size="small" link @click="handleDeleteCourse(row)">
                    删除
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="pagination-wrapper">
          <el-pagination
            v-model:current-page="currentPage"
            background
            layout="total, prev, pager, next"
            :total="total"
            :page-size="pageSize"
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
      <el-form ref="typeFormRef" :model="typeForm" :rules="typeRules" label-width="110px">
        <el-form-item label="类型名称" prop="name">
          <el-input v-model="typeForm.name" placeholder="如：常规课、特色课、私教课" />
        </el-form-item>
        <el-form-item label="类型代码" prop="code">
          <el-input
            v-model="typeForm.code"
            placeholder="如：regular、special、private"
            :disabled="isTypeEdit"
          />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="typeForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入描述"
          />
        </el-form-item>
        <el-form-item label="排序" prop="sort_order">
          <el-input-number v-model="typeForm.sort_order" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-radio-group v-model="typeForm.status">
            <el-radio :value="1"> 启用 </el-radio>
            <el-radio :value="0"> 禁用 </el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="最低成课人数" prop="min_students">
          <el-input-number
            v-model="typeForm.min_students"
            :min="1"
            :max="50"
            placeholder="留空表示不限制"
            clearable
            style="width: 100%"
          />
          <div class="form-tip">仅对常规课生效，预约截止时人数不足将自动取消课程</div>
        </el-form-item>
        <el-form-item label="开课前禁止取消" prop="cancel_before_minutes">
          <el-input-number
            v-model="typeForm.cancel_before_minutes"
            :min="0"
            :max="1440"
            placeholder="留空表示不限制"
            clearable
            style="width: 100%"
          />
          <div class="form-tip">开课前多少分钟不能取消课程，同时用于判断人数是否足够的截止时间</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="typeDialogVisible = false"> 取消 </el-button>
        <el-button type="primary" :loading="typeSubmitting" @click="handleTypeSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 舞蹈分类对话框 -->
    <el-dialog
      v-model="categoryDialogVisible"
      :title="isCategoryEdit ? '编辑' : '新增'"
      width="560px"
      :close-on-click-modal="false"
      @close="handleCategoryDialogClose"
    >
      <el-form
        ref="categoryFormRef"
        :model="categoryForm"
        :rules="categoryRules"
        label-width="100px"
      >
        <el-form-item label="分类名称" prop="name">
          <el-input v-model="categoryForm.name" placeholder="请输入分类名称" />
        </el-form-item>
        <el-form-item label="分类代码" prop="code">
          <el-input v-model="categoryForm.code" placeholder="请输入分类代码（英文）" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="categoryForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入分类描述/介绍"
          />
        </el-form-item>
        <el-form-item label="排序" prop="sort_order">
          <el-input-number v-model="categoryForm.sort_order" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-radio-group v-model="categoryForm.status">
            <el-radio :value="1"> 启用 </el-radio>
            <el-radio :value="0"> 禁用 </el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="categoryDialogVisible = false"> 取消 </el-button>
        <el-button type="primary" :loading="categorySubmitting" @click="handleCategorySubmit">
          确定
        </el-button>
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
          <el-select
            v-model="courseForm.course_type_code"
            placeholder="请选择课程类型"
            style="width: 100%"
          >
            <el-option
              v-for="type in courseTypes"
              :key="type.code"
              :label="type.name"
              :value="type.code"
              :disabled="type.status !== 1"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="舞蹈分类" prop="category">
          <el-select
            v-model="courseForm.category"
            placeholder="请选择舞蹈分类"
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="cat in courseCategories"
              :key="cat.code"
              :label="cat.name"
              :value="cat.code"
              :disabled="cat.status !== 1"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="难度等级" prop="level">
          <el-select
            v-model="courseForm.level"
            placeholder="请选择或输入难度"
            clearable
            allow-create
            style="width: 100%"
          >
            <el-option label="入门" value="入门" />
            <el-option label="初级" value="初级" />
            <el-option label="中级" value="中级" />
            <el-option label="高级" value="高级" />
          </el-select>
        </el-form-item>
        <el-form-item label="时长(分钟)" prop="duration_minutes">
          <el-input-number
            v-model="courseForm.duration_minutes"
            :min="1"
            :max="480"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="课程描述" prop="description">
          <el-input
            v-model="courseForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入课程描述"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="courseDialogVisible = false"> 取消 </el-button>
        <el-button type="primary" :loading="courseSubmitting" @click="handleCourseSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import {
  courseApi,
  courseCategoryApi,
  courseTypeApi,
  type Course,
  type CourseCategory,
  type CourseCategoryCreateParams,
  type CourseCategoryUpdateParams,
  type CourseCreateParams,
  type CourseType,
  type CourseTypeCreateParams,
  type CourseTypeUpdateParams,
  type CourseUpdateParams,
} from '@dance-saas/api-client'
import {
  Delete,
  Edit,
  Folder,
  Medal,
  Microphone,
  Search,
  Star,
  User,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

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
  min_students: undefined,
  cancel_before_minutes: undefined,
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
    courseTypes.value = Array.isArray(data) ? data : data.items || []
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

function selectCategory(cat: CourseCategory | null) {
  selectedCategoryCode.value = cat ? cat.code : null
  currentPage.value = 1
  fetchCourses()
}

function clearAllFilters() {
  selectedTypeCode.value = null
  selectedCategoryCode.value = null
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
    min_students: undefined,
    cancel_before_minutes: undefined,
  }
  typeDialogVisible.value = true
  typeFormRef.value?.clearValidate()
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
    min_students: (row as any).min_students ?? undefined,
    cancel_before_minutes: (row as any).cancel_before_minutes ?? undefined,
  }
  typeDialogVisible.value = true
  typeFormRef.value?.clearValidate()
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
    await ElMessageBox.confirm(
      `确定要删除课程类型「${row.name}」吗？如有课程使用此类型则无法删除。`,
      '警告',
      { type: 'error' }
    )
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

// ==================== 舞蹈分类相关 ====================
const categoryTab = ref('type')
const categoryLoading = ref(false)
const categorySubmitting = ref(false)
const courseCategories = ref<CourseCategory[]>([])
const selectedCategoryCode = ref<string | null>(null)

const categoryDialogVisible = ref(false)
const isCategoryEdit = ref(false)
const editingCategoryId = ref<number | null>(null)
const categoryFormRef = ref()

const categoryForm = ref<CourseCategoryCreateParams>({
  name: '',
  code: '',
  description: '',
  sort_order: 0,
  status: 1,
})

const categoryRules = {
  name: [{ required: true, message: '请输入分类名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入分类代码', trigger: 'blur' }],
}

function onCategoryTabChange() {
  if (categoryTab.value === 'category' && courseCategories.value.length === 0) {
    fetchCourseCategories()
  }
}

function handleAddClick() {
  if (categoryTab.value === 'type') {
    openTypeCreateDialog()
  } else {
    openCategoryCreateDialog()
  }
}

async function fetchCourseCategories() {
  categoryLoading.value = true
  try {
    const res = await courseCategoryApi.list({ status: undefined })
    courseCategories.value = res.data.items || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '加载舞蹈分类失败')
  } finally {
    categoryLoading.value = false
  }
}

function openCategoryCreateDialog() {
  isCategoryEdit.value = false
  editingCategoryId.value = null
  categoryForm.value = {
    name: '',
    code: '',
    description: '',
    sort_order: 0,
    status: 1,
  }
  categoryDialogVisible.value = true
  categoryFormRef.value?.clearValidate()
}

function openCategoryEditDialog(row: CourseCategory) {
  isCategoryEdit.value = true
  editingCategoryId.value = row.id
  categoryForm.value = {
    name: row.name,
    code: row.code,
    description: row.description || '',
    sort_order: row.sort_order,
    status: row.status,
  }
  categoryDialogVisible.value = true
  categoryFormRef.value?.clearValidate()
}

function handleCategoryDialogClose() {
  categoryFormRef.value?.clearValidate()
}

async function handleCategorySubmit() {
  const valid = await categoryFormRef.value?.validate().catch(() => false)
  if (!valid) return

  categorySubmitting.value = true
  try {
    if (isCategoryEdit.value && editingCategoryId.value) {
      await courseCategoryApi.update(
        editingCategoryId.value,
        categoryForm.value as CourseCategoryUpdateParams
      )
      ElMessage.success('舞蹈分类更新成功')
    } else {
      await courseCategoryApi.create(categoryForm.value)
      ElMessage.success('舞蹈分类创建成功')
    }
    categoryDialogVisible.value = false
    fetchCourseCategories()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '操作失败')
  } finally {
    categorySubmitting.value = false
  }
}

async function handleDeleteCategory(row: CourseCategory) {
  try {
    await ElMessageBox.confirm(
      `确定要删除舞蹈分类「${row.name}」吗？如有课程使用此分类则无法删除。`,
      '警告',
      { type: 'error' }
    )
    await courseCategoryApi.remove(row.id)
    ElMessage.success('删除成功')
    if (selectedCategoryCode.value === row.code) {
      selectedCategoryCode.value = null
    }
    fetchCourseCategories()
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
      category: selectedCategoryCode.value || undefined,
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

function handlePageSizeChange() {
  currentPage.value = 1
  fetchCourses()
}

function getLevelStars(level: string | undefined): number {
  const map: Record<string, number> = {
    入门: 1,
    初级: 2,
    中级: 3,
    高级: 4,
  }
  return map[level || ''] || 0
}

function getCategoryTagType(category: string | undefined): string {
  const map: Record<string, string> = {
    ballet: 'danger',
    jazz: 'primary',
    street: 'warning',
    latin: 'success',
    modern: 'danger',
    yoga: 'primary',
    children: 'warning',
    adult: 'success',
    exam: 'danger',
    hobby: 'primary',
  }
  return map[category || ''] || 'info'
}

function getCategoryName(code: string | undefined): string | undefined {
  if (!code) return undefined
  const cat = courseCategories.value.find(c => c.code === code)
  return cat?.name || code
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
    category: selectedCategoryCode.value || undefined,
    level: undefined,
    duration_minutes: 60,
    description: '',
  }
  courseDialogVisible.value = true
  courseFormRef.value?.clearValidate()
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
    description: row.description || '',
  }
  courseDialogVisible.value = true
  courseFormRef.value?.clearValidate()
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
    await ElMessageBox.confirm(`确定要${action}课程「${row.name}」吗？`, '提示', {
      type: 'warning',
    })
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
    await ElMessageBox.confirm(`确定要删除课程「${row.name}」吗？此操作不可恢复。`, '警告', {
      type: 'error',
    })
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
  fetchCourseCategories()
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
  width: 320px;
  flex-shrink: 0;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #ebeef5;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* ===== 当前筛选条件提示 ===== */
.active-filters {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  margin-bottom: 12px;
  background: #f5f7fa;
  border-radius: 8px;
  flex-wrap: wrap;
}

.filter-label {
  font-size: 13px;
  color: #909399;
  white-space: nowrap;
}

.panel-tabs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}

.panel-tabs-header .category-tabs {
  flex: 1;
  min-width: 0;
}

.panel-tabs-header .category-tabs :deep(.el-tabs__header) {
  margin-bottom: 0;
}

.panel-tabs-header .category-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 0;
}

.panel-tabs-header .category-tabs :deep(.el-tabs__item) {
  color: #606266;
  font-weight: 500;
}

.panel-tabs-header .category-tabs :deep(.el-tabs__item.is-active) {
  color: #409eff;
  font-weight: 600;
}

.panel-tabs-header .category-tabs :deep(.el-tabs__active-bar) {
  background-color: #409eff;
}

.panel-tabs-header .el-button {
  flex-shrink: 0;
  margin-left: 8px;
}

.panel-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.category-list {
  padding: 8px;
  flex: 1;
  overflow-y: auto;

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

.icon-category {
  background: #fdf6ec;
  color: #e6a23c;
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

.filter-bar-actions {
  margin-left: auto;
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

.search-icon:hover {
  color: #409eff;
}

.form-tip {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}
</style>
