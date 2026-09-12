<template>
  <div class="page-container">
    <div class="page-header">
      <h2>卡类型管理</h2>
      <el-button type="primary" @click="openCreateDialog">
        新增
      </el-button>
    </div>

    <!-- 正常列表 -->
    <el-table :data="cardTypes" stripe style="width:100%" v-loading="loading">
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="name" label="类型名称" min-width="120" />
      <el-table-column prop="card_type" label="卡类型" width="100">
        <template #default="{ row }">
          <el-tag :type="getCardTypeTag(row.card_type)" size="small">
            {{ getCardTypeText(row.card_type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="total_credits" label="包含次数" width="100">
        <template #default="{ row }">
          {{ row.card_type === 'count' ? row.total_credits : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="validity_days" label="有效天数" width="100">
        <template #default="{ row }">
          {{ (row.card_type === 'count' || row.card_type === 'period') ? row.validity_days : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="price" label="价格(元)" width="100" />
      <el-table-column prop="applicable_course_type_codes" label="适用课程类型" min-width="180">
        <template #default="{ row }">
          <template v-if="row.applicable_course_type_codes && row.applicable_course_type_codes.length > 0">
            <el-tag
              v-for="code in row.applicable_course_type_codes"
              :key="code"
              size="small"
              style="margin-right:4px"
            >
              {{ getCourseTypeName(code) }}
            </el-tag>
          </template>
          <span v-else style="color:#909399">不限</span>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
            {{ row.status === 1 ? '上架' : '下架' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button v-if="isAdmin" type="primary" size="small" link @click="openEditDialog(row)">编辑</el-button>
          <el-button
            :type="row.status === 1 ? 'warning' : 'success'"
            size="small"
            link
            @click="toggleStatus(row)"
          >{{ row.status === 1 ? '下架' : '上架' }}</el-button>
          <el-button v-if="row.status === 0" type="danger" size="small" link @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrapper">
      <el-pagination
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        v-model:current-page="currentPage"
        @current-change="fetchCardTypes"
      />
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑' : '新增'"
      width="560px"
      :close-on-click-modal="false"
      @close="handleDialogClose"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-form-item label="类型名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入类型名称" />
        </el-form-item>
        <el-form-item label="卡类型" prop="card_type">
          <el-select v-model="form.card_type" placeholder="请选择卡类型" style="width:100%">
            <el-option label="次卡" value="count" />
            <el-option label="期卡" value="period" />
            <el-option label="无限卡" value="unlimited" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.card_type === 'count'" label="包含次数" prop="total_credits">
          <el-input-number v-model="form.total_credits" :min="1" style="width:100%" />
        </el-form-item>
        <el-form-item v-if="form.card_type === 'count' || form.card_type === 'period'" label="有效天数" prop="validity_days">
          <el-input-number v-model="form.validity_days" :min="1" style="width:100%" />
        </el-form-item>
        <el-form-item label="价格(元)" prop="price">
          <el-input-number v-model="form.price" :min="0" :precision="2" style="width:100%" />
        </el-form-item>
        <el-form-item label="适用课程类型" prop="applicable_course_type_codes">
          <el-select v-model="form.applicable_course_type_codes" placeholder="请选择适用的课程类型（至少选择一项）" multiple style="width:100%">
            <el-option
              v-for="type in courseTypes"
              :key="type.code"
              :label="type.name"
              :value="type.code"
              :disabled="type.status !== 1"
            />
          </el-select>
          <div style="margin-top:4px;color:#909399;font-size:12px">
            必填项：选择后学员只能约选中的课程类型，请根据产品定位选择
          </div>
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请输入描述" />
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
import { ref, computed, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { cardTypeApi, courseTypeApi, type MembershipCardProduct, type MembershipCardProductCreateParams, type MembershipCardProductUpdateParams, type CourseType } from '@dance-saas/api-client'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

const loading = ref(false)
const submitting = ref(false)
const cardTypes = ref<MembershipCardProduct[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const courseTypes = ref<CourseType[]>([])

const dialogVisible = ref(false)
const isEdit = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref()

const form = ref<MembershipCardProductCreateParams>({
  name: '',
  card_type: 'count',
  total_credits: undefined,
  validity_days: undefined,
  price: 0,
  applicable_course_type_codes: [],
  description: '',
  sort_order: 0,
})

const rules = computed(() => {
  const baseRules: any = {
    name: [{ required: true, message: '请输入产品名称', trigger: 'blur' }],
    card_type: [{ required: true, message: '请选择卡类型', trigger: 'change' }],
    price: [{ required: true, message: '请输入价格', trigger: 'blur' }],
    applicable_course_type_codes: [
      { 
        type: 'array' as const, 
        required: true, 
        message: '请至少选择一项适用的课程类型', 
        trigger: 'change',
      },
    ],
  }

  // 根据卡类型动态添加必填验证
  if (form.value.card_type === 'count') {
    baseRules.total_credits = [{ required: true, message: '请输入包含次数', trigger: 'blur' }]
    baseRules.validity_days = [{ required: true, message: '请输入有效天数', trigger: 'blur' }]
  } else if (form.value.card_type === 'period') {
    baseRules.validity_days = [{ required: true, message: '请输入有效天数', trigger: 'blur' }]
  }

  return baseRules
})

const cardTypeMap: Record<string, string> = {
  count: '次卡',
  period: '期卡',
  unlimited: '无限卡',
}

const isAdmin = computed(() => authStore.hasRole('admin') || authStore.hasRole('super_admin'))

const cardTypeTagMap: Record<string, 'success' | 'warning' | 'info'> = {
  count: 'success',
  period: 'warning',
  unlimited: 'info',
}

function getCardTypeText(type: string) {
  return cardTypeMap[type] || type
}

function getCardTypeTag(type: string) {
  return cardTypeTagMap[type] || 'info'
}

function getCourseTypeName(code: string) {
  const type = courseTypes.value.find(t => t.code === code)
  return type ? type.name : code
}

async function fetchCardTypes() {
  loading.value = true
  try {
    const res = await cardTypeApi.list({
      page: currentPage.value,
      page_size: pageSize.value,
    })
    cardTypes.value = res.data.items
    total.value = res.data.total
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '加载卡类型列表失败')
  } finally {
    loading.value = false
  }
}

function openCreateDialog() {
  isEdit.value = false
  editingId.value = null
  form.value = {
    name: '',
    card_type: 'count',
    total_credits: undefined,
    validity_days: undefined,
    price: 0,
    applicable_course_type_codes: [],
    description: '',
    sort_order: 0,
  }
  dialogVisible.value = true
}

function openEditDialog(row: MembershipCardProduct) {
  isEdit.value = true
  editingId.value = row.id
  form.value = {
    name: row.name,
    card_type: row.card_type,
    total_credits: row.total_credits ?? undefined,
    validity_days: row.validity_days ?? undefined,
    price: row.price,
    applicable_course_type_codes: row.applicable_course_type_codes || [],
    description: row.description || '',
    sort_order: row.sort_order,
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
      await cardTypeApi.update(editingId.value, form.value as MembershipCardProductUpdateParams)
      ElMessage.success('卡类型更新成功')
    } else {
      await cardTypeApi.create(form.value)
      ElMessage.success('卡类型创建成功')
    }
    dialogVisible.value = false
    fetchCardTypes()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function toggleStatus(row: MembershipCardProduct) {
  const newStatus = row.status === 1 ? 0 : 1
  const action = newStatus === 0 ? '下架' : '上架'
  try {
    await ElMessageBox.confirm(`确定要${action}卡类型「${row.name}」吗？`, '提示', { type: 'warning' })
    await cardTypeApi.update(row.id, { status: newStatus })
    ElMessage.success(`${action}成功`)
    fetchCardTypes()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.msg || '操作失败')
    }
  }
}

async function handleDelete(row: MembershipCardProduct) {
  try {
    await ElMessageBox.confirm(`确定要删除卡类型「${row.name}」吗？`, '警告', { type: 'warning' })
    await cardTypeApi.remove(row.id)
    ElMessage.success('删除成功')
    fetchCardTypes()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.msg || '删除失败')
    }
  }
}

async function fetchCourseTypes() {
  try {
    const res = await courseTypeApi.list()
    const data = res.data as any
    courseTypes.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e: any) {
    console.error('加载课程类型失败', e)
  }
}

onMounted(() => {
  fetchCardTypes()
  fetchCourseTypes()
})
</script>