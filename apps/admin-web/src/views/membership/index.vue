<template>
  <div class="page-container">
    <div class="page-header">
      <h2>会员卡管理</h2>
      <el-button type="primary" @click="openCreateDialog">
        发放会员卡
      </el-button>
    </div>

    <div style="display:flex;gap:12px;margin-bottom:16px">
      <el-input v-model="search" placeholder="搜索学员或手机号" style="width:200px" clearable @keyup.enter="handleSearch" @clear="handleSearch" />
      <el-select v-model="statusFilter" placeholder="状态筛选" style="width:120px" clearable @change="handleSearch">
        <el-option label="未激活" :value="0" />
        <el-option label="正常" :value="1" />
        <el-option label="已冻结" :value="2" />
        <el-option label="已过期" :value="3" />
      </el-select>
    </div>

    <el-table :data="cards" stripe style="width:100%" v-loading="loading">
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="product_name" label="产品名称" min-width="120" />
      <el-table-column prop="card_type" label="卡类型" width="100">
        <template #default="{ row }">
          {{ getCardTypeText(row.card_type) }}
        </template>
      </el-table-column>
      <el-table-column prop="student_nickname" label="学员" width="100" />
      <el-table-column prop="student_phone" label="手机号" width="120" />
      <el-table-column prop="total_credits" label="总次数" width="80">
        <template #default="{ row }">
          {{ row.card_type === 'count' ? row.total_credits : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="used_credits" label="已用" width="80">
        <template #default="{ row }">
          {{ row.card_type === 'count' ? row.used_credits : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="remaining_credits" label="剩余" width="80">
        <template #default="{ row }">
          {{ row.card_type === 'count' ? row.remaining_credits : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)" size="small">
            {{ getStatusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="valid_from" label="生效时间" width="160">
        <template #default="{ row }">
          {{ row.valid_from ? formatDate(row.valid_from) : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="expire_at" label="过期时间" width="160">
        <template #default="{ row }">
          {{ row.expire_at ? formatDate(row.expire_at) : '-' }}
        </template>
      </el-table-column>
      <el-table-column label="冻结信息" width="200" v-if="hasFrozenCard">
        <template #default="{ row }">
          <template v-if="row.status === 3">
            <div style="line-height:1.6">
              <div>已冻结 {{ getFrozenDuration(row) }}</div>
              <div style="color:#E6A23C;font-size:12px">
                剩余 {{ getFrozenRemainingDays(row) }} 天
              </div>
            </div>
          </template>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" link @click="openDetailDialog(row)">详情</el-button>
          <el-button v-if="row.status === 0" type="success" size="small" link @click="handleActivate(row)">激活</el-button>
          <el-button v-if="row.status === 1" type="warning" size="small" link @click="openFreezeDialog(row)">冻结</el-button>
          <el-button v-if="row.status === 3" type="success" size="small" link @click="handleUnfreeze(row)">提前解冻</el-button>
          <el-button v-if="row.status !== 6" type="danger" size="small" link @click="openCancelDialog(row)">作废</el-button>
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
        @current-change="fetchCards"
      />
    </div>

    <el-dialog
      v-model="dialogVisible"
      title="发放会员卡"
      width="560px"
      :close-on-click-modal="false"
      @close="handleDialogClose"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="学员" prop="student_id">
          <el-select v-model="form.student_id" placeholder="请选择学员" filterable remote :remote-method="handleSearchStudent" style="width:100%" @change="handleStudentChange">
            <el-option v-for="user in users" :key="user.id" :label="`${user.nickname || '-'} (${user.phone})`" :value="user.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="产品" prop="product_id">
          <el-select v-model="form.product_id" placeholder="请选择产品" style="width:100%" @change="handleProductChange">
            <el-option v-for="product in products" :key="product.id" :label="product.name" :value="product.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="selectedProduct?.card_type === 'count'" label="总次数">
          <el-input-number v-model="form.total_credits" :min="1" disabled style="width:100%" />
          <span style="margin-left:8px;color:#909399;font-size:12px">次数由产品决定，不可修改</span>
        </el-form-item>
        <el-form-item v-if="selectedProduct?.card_type === 'count'" label="有效天数">
          <el-input-number v-model="form.validity_days" :min="1" disabled style="width:100%" />
          <span style="margin-left:8px;color:#909399;font-size:12px">天数由产品决定，不可修改</span>
        </el-form-item>
        <el-form-item v-if="selectedProduct?.card_type === 'period'" label="有效天数">
          <el-input-number v-model="form.validity_days" :min="1" disabled style="width:100%" />
          <span style="margin-left:8px;color:#909399;font-size:12px">天数由产品决定，不可修改</span>
        </el-form-item>
        <el-form-item v-if="selectedProduct?.card_type === 'unlimited'" label="卡类型">
          <el-tag type="success">无限卡</el-tag>
          <span style="margin-left:8px;color:#909399;font-size:12px">无限卡无次数和天数限制</span>
        </el-form-item>
        <el-form-item label="生效时间" prop="valid_from">
          <el-date-picker
            v-model="form.valid_from"
            type="date"
            placeholder="选择生效日期（留空表示立即激活）"
            style="width:100%"
            clearable
            :disabled-date="disabledDate"
            value-format="YYYY-MM-DD"
          />
          <div v-if="minValidDate" style="margin-top:4px;color:#E6A23C;font-size:12px">
            因学员已有有效卡，最早可选日期：<strong>{{ minValidDate }}</strong>
          </div>
          <div v-else style="margin-top:4px;color:#909399;font-size:12px">
            选择日期后，生效时间将为当天的 00:00:00，到期时间为有效期最后一天的 23:59:59
          </div>
        </el-form-item>
        <el-form-item label="备注" prop="remark">
          <el-input v-model="form.remark" type="textarea" :rows="3" placeholder="请输入备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailDialogVisible" title="会员卡详情" width="600px">
      <el-descriptions :column="2" border v-if="detailCard">
        <el-descriptions-item label="产品名称">{{ detailCard.product_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="卡类型">{{ getCardTypeText(detailCard.card_type) }}</el-descriptions-item>
        <el-descriptions-item label="学员">{{ detailCard.student_nickname || '-' }}</el-descriptions-item>
        <el-descriptions-item label="手机号">{{ detailCard.student_phone || '-' }}</el-descriptions-item>
        <template v-if="detailCard.card_type === 'count'">
          <el-descriptions-item label="总次数">{{ detailCard.total_credits ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="已用次数">{{ detailCard.used_credits ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="剩余次数">{{ detailCard.remaining_credits ?? '-' }}</el-descriptions-item>
        </template>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(detailCard.status)" size="small">
            {{ getStatusText(detailCard.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="生效时间">{{ detailCard.valid_from ? formatDate(detailCard.valid_from) : '-' }}</el-descriptions-item>
        <el-descriptions-item label="过期时间">{{ detailCard.expire_at ? formatDate(detailCard.expire_at) : '-' }}</el-descriptions-item>
        <template v-if="detailCard.status === 3">
          <el-descriptions-item label="冻结时间">{{ detailCard.frozen_at ? formatDate(detailCard.frozen_at) : '-' }}</el-descriptions-item>
          <el-descriptions-item label="冻结到期">{{ detailCard.frozen_until ? formatDate(detailCard.frozen_until) : '-' }}</el-descriptions-item>
          <el-descriptions-item label="已冻结时长" :span="2">
            {{ getFrozenDuration(detailCard) }}
          </el-descriptions-item>
          <el-descriptions-item label="剩余冻结天数" :span="2">
            <span style="color:#E6A23C;font-weight:600">{{ getFrozenRemainingDays(detailCard) }} 天</span>
          </el-descriptions-item>
          <el-descriptions-item label="冻结原因" :span="2">{{ detailCard.frozen_reason || '-' }}</el-descriptions-item>
        </template>
        <el-descriptions-item v-else label="冻结原因" :span="2">{{ detailCard.frozen_reason || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">{{ detailCard.created_at ? formatDate(detailCard.created_at) : '-' }}</el-descriptions-item>
        <el-descriptions-item label="更新时间" :span="2">{{ detailCard.updated_at ? formatDate(detailCard.updated_at) : '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <el-dialog v-model="freezeDialogVisible" title="冻结会员卡" width="460px" :close-on-click-modal="false">
      <el-form ref="freezeFormRef" :model="freezeForm" :rules="freezeRules" label-width="100px">
        <el-form-item label="冻结天数" prop="freeze_days">
          <el-input-number v-model="freezeForm.freeze_days" :min="1" :max="365" style="width:100%" />
          <span style="margin-left:8px;color:#909399;font-size:12px">1-365天</span>
        </el-form-item>
        <el-form-item label="冻结原因" prop="reason">
          <el-input v-model="freezeForm.reason" type="textarea" :rows="3" placeholder="请输入冻结原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="freezeDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleFreeze" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="cancelDialogVisible" title="作废会员卡" width="460px" :close-on-click-modal="false">
      <el-form ref="cancelFormRef" :model="cancelForm" label-width="100px">
        <el-form-item label="作废原因" prop="reason">
          <el-input v-model="cancelForm.reason" type="textarea" :rows="3" placeholder="请输入作废原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cancelDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="handleCancel" :loading="submitting">确定作废</el-button>
      </template>
    </el-dialog>

    <!-- 续卡提示对话框 -->
    <el-dialog v-model="renewalDialogVisible" title="" width="480px" :show-close="true" :close-on-click-modal="false" custom-class="renewal-dialog">
      <div class="renewal-content">
        <div class="renewal-header">
          <span class="renewal-icon">⚠️</span>
          <span class="renewal-title">该学员已有 {{ renewalCardCount }} 张同类型有效卡</span>
        </div>
        <div class="renewal-subtitle">如需继续发卡（续卡），请确认以下规则：</div>
        <div class="renewal-rules">
          <div class="rules-title"> 续卡规则</div>
          <div class="rules-item">• 新卡生效时间必须晚于旧卡到期时间的次日</div>
          <div v-if="renewalEarliestDate" class="rules-hint">✅ 系统已自动设置最早生效日期：<strong>{{ renewalEarliestDate }}</strong></div>
        </div>
        <div class="renewal-footer">请确认生效时间后，重新点击"确定"按钮</div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { membershipCardApi, cardTypeApi, type MembershipCard, type MembershipCardCreateParams, type MembershipCardProduct } from '@dance-saas/api-client'
import { userApi } from '@dance-saas/api-client'

const loading = ref(false)
const submitting = ref(false)
const cards = ref<MembershipCard[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const search = ref('')
const statusFilter = ref<number | undefined>(undefined)
const users = ref<any[]>([])
const products = ref<MembershipCardProduct[]>([])

const hasFrozenCard = computed(() => cards.value.some(c => c.status === 3))

const dialogVisible = ref(false)
const formRef = ref()
const selectedProduct = ref<any>(null)
const minValidDate = ref<string | null>(null)

const form = ref<MembershipCardCreateParams>({
  student_id: undefined,
  product_id: undefined,
  total_credits: undefined,
  validity_days: undefined,
  valid_from: undefined,
  allow_duplicate: false,
  remark: '',
})

const rules = {
  student_id: [{ required: true, message: '请选择学员', trigger: 'change' }],
  product_id: [{ required: true, message: '请选择产品', trigger: 'change' }],
}

const freezeDialogVisible = ref(false)
const freezeFormRef = ref()
const freezeForm = ref({ reason: '', freeze_days: 7 })
const freezingCardId = ref<number | null>(null)

const freezeRules = {
  freeze_days: [{ required: true, message: '请输入冻结天数', trigger: 'blur' }],
  reason: [{ required: true, message: '请输入冻结原因', trigger: 'blur' }],
}

const cancelDialogVisible = ref(false)
const cancelFormRef = ref()
const cancelForm = ref({ reason: '' })
const cancelingCardId = ref<number | null>(null)

const renewalDialogVisible = ref(false)
const renewalCardCount = ref('')
const renewalEarliestDate = ref<string | null>(null)

const detailDialogVisible = ref(false)
const detailCard = ref<MembershipCard | null>(null)

async function fetchCards() {
  loading.value = true
  try {
    const params: any = {
      page: currentPage.value,
      page_size: pageSize.value,
      status: statusFilter.value,
    }
    if (search.value) {
      params.keyword = search.value
    }
    const res = await membershipCardApi.list(params)
    cards.value = res.data.items
    total.value = res.data.total
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '加载会员卡列表失败')
  } finally {
    loading.value = false
  }
}

async function fetchUsers(keyword?: string) {
  try {
    const params: any = { page: 1, page_size: 100, role_code: 'student' }
    if (keyword) {
      params.keyword = keyword
    }
    const res = await userApi.list(params)
    // API client 已解包，res.data 就是 { items: [...], total: ... }
    users.value = res.data?.items || []
    console.log('✅ 学员列表加载成功，数量:', users.value.length)
  } catch (e: any) {
    console.error('❌ 加载学员列表失败', e)
    ElMessage.error('加载学员列表失败')
  }
}

async function fetchProducts() {
  try {
    const res = await cardTypeApi.list({ page: 1, page_size: 100, status: 1 })
    products.value = res.data.items
    console.log('✅ 已上架产品列表加载成功，数量:', products.value.length)
    console.log('📦 产品数据示例:', products.value[0])
  } catch (e: any) {
    console.error(' 加载产品列表失败', e)
  }
}

function handleSearch() {
  currentPage.value = 1
  fetchCards()
  fetchUsers()
}

function handleSearchStudent(keyword: string) {
  fetchUsers(keyword)
}

function disabledDate(time: Date) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  
  // 如果有最早生效日期限制，则禁用该日期之前的所有日期
  if (minValidDate.value) {
    const minDate = new Date(minValidDate.value)
    minDate.setHours(0, 0, 0, 0)
    return time.getTime() < minDate.getTime()
  }
  
  // 否则只允许选择今天及之后的日期
  return time.getTime() < today.getTime()
}

function openCreateDialog() {
  minValidDate.value = null
  form.value = {
    student_id: undefined,
    product_id: undefined,
    total_credits: undefined,
    validity_days: undefined,
    valid_from: undefined,
    allow_duplicate: false,
    remark: '',
  }
  users.value = []
  dialogVisible.value = true
}

function handleStudentChange() {
  // 清空之前设置的生效时间
  form.value.valid_from = undefined
  // 清空最早可选日期限制
  minValidDate.value = null
  // 重置 allow_duplicate 标志
  form.value.allow_duplicate = false
}

function handleProductChange(productId: number) {
  const product = products.value.find(p => p.id === productId)
  if (!product) return

  selectedProduct.value = product
  console.log('📦 选择产品:', product.name, '次数:', product.total_credits, '天数:', product.validity_days)

  // 自动带入产品信息
  form.value.total_credits = product.total_credits ?? undefined
  form.value.validity_days = product.validity_days ?? undefined

  console.log('✅ 表单已更新 - 总次数:', form.value.total_credits, '有效天数:', form.value.validity_days)
}

function openDetailDialog(row: MembershipCard) {
  detailCard.value = row
  detailDialogVisible.value = true
}

function handleDialogClose() {
  formRef.value?.clearValidate()
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const payload: any = { ...form.value }
    // 移除 undefined 值
    Object.keys(payload).forEach(key => {
      if (payload[key] === undefined) {
        delete payload[key]
      }
    })
    // valid_from 已经是 YYYY-MM-DD 格式，不需要转换
    // 后端会自动将其转为 datetime 并设置时分秒为 00:00:00
    console.log('📤 发送请求数据:', payload)
    await membershipCardApi.create(payload)
    ElMessage.success('会员卡发放成功')
    dialogVisible.value = false
    fetchCards()
  } catch (e: any) {
    console.error('❌ 发放会员卡失败:', e)
    console.error('  请求数据:', e?.config?.data)
    console.error('  响应数据:', e?.response?.data)
    
    const status = e?.response?.status
    // 兼容后端返回的 detail 和 msg 字段
    const errorMsg = e?.response?.data?.detail || e?.response?.data?.msg || '操作失败'
    
    // 根据不同状态码给出详细提示
    if (status === 409) {
      // 重复发卡冲突 - 提示用户修改生效时间后重新提交
      const match = errorMsg.match(/(\d{4}-\d{2}-\d{2})/)
      const earliestDate = match ? match[1] : null
      
      // 提取已有卡数量（如果有）
      const countMatch = errorMsg.match(/(\d+)\s*张/)
      const cardCount = countMatch ? countMatch[1] : ''
      
      // 设置续卡对话框数据
      renewalCardCount.value = cardCount
      renewalEarliestDate.value = earliestDate
      renewalDialogVisible.value = true
      
      // 设置 allow_duplicate=true，允许用户重新提交（用户无需感知此参数）
      form.value.allow_duplicate = true
      
      // 如果后端返回了最早生效日期，自动设置到表单中并禁用之前的日期
      if (earliestDate) {
        minValidDate.value = earliestDate
        form.value.valid_from = earliestDate
      }
      
      // 不关闭对话框，让用户修改后重新提交
      submitting.value = false
      return
    } else if (status === 403) {
      // 权限错误
      ElMessage.error(`❌ 权限不足：${errorMsg}\n\n请联系管理员确认您的操作权限。`)
    } else if (status === 400) {
      // 业务参数错误
      ElMessage.error(`❌ 参数错误：${errorMsg}`)
    } else if (status === 404) {
      // 资源不存在
      ElMessage.error(`❌ 资源不存在：${errorMsg}`)
    } else if (status === 500) {
      // 服务器错误
      ElMessage.error('❌ 服务器内部错误，请联系技术人员处理。')
    } else {
      // 其他错误
      ElMessage.error(`❌ 操作失败（HTTP ${status}）：${errorMsg}`)
    }
  } finally {
    submitting.value = false
  }
}

async function handleActivate(row: MembershipCard) {
  try {
    await ElMessageBox.confirm(`确定要激活会员卡「${row.product_name || '-'}」吗？`, '提示', { type: 'warning' })
    await membershipCardApi.adminActivate(row.id)
    ElMessage.success('激活成功')
    fetchCards()
  } catch (e: any) {
    if (e !== 'cancel') {
      const status = e?.response?.status
      const errorMsg = e?.response?.data?.detail || e?.response?.data?.msg || '激活失败'
      
      if (status === 409) {
        // 重复卡冲突 - 给出明确的操作指引
        ElMessage({
          message: `${errorMsg}`,
          type: 'warning',
          duration: 5000,
          showClose: true,
        })
      } else {
        ElMessage.error(`❌ ${errorMsg}`)
      }
    }
  }
}

function openFreezeDialog(row: MembershipCard) {
  freezingCardId.value = row.id
  freezeForm.value = { reason: '', freeze_days: 7 }
  freezeDialogVisible.value = true
}

async function handleFreeze() {
  const valid = await freezeFormRef.value?.validate().catch(() => false)
  if (!valid || !freezingCardId.value) return

  submitting.value = true
  try {
    await membershipCardApi.freeze(freezingCardId.value, {
      reason: freezeForm.value.reason,
      freeze_days: freezeForm.value.freeze_days,
    })
    ElMessage.success('冻结成功')
    freezeDialogVisible.value = false
    fetchCards()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '冻结失败')
  } finally {
    submitting.value = false
  }
}

async function handleUnfreeze(row: MembershipCard) {
  try {
    await ElMessageBox.confirm(
      `确定要提前解冻学员「${row.student_nickname || '未知'}」的会员卡吗？解冻后卡片将立即恢复正常使用。`,
      '提前解冻确认',
      {
        confirmButtonText: '确定解冻',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    await membershipCardApi.unfreeze(row.id)
    ElMessage.success('解冻成功')
    fetchCards()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.msg || '解冻失败')
    }
  }
}

function openCancelDialog(row: MembershipCard) {
  cancelingCardId.value = row.id
  cancelForm.value = { reason: '' }
  cancelDialogVisible.value = true
}

async function handleCancel() {
  if (!cancelingCardId.value || !cancelForm.value.reason) {
    ElMessage.warning('请输入作废原因')
    return
  }
  submitting.value = true
  try {
    await membershipCardApi.cancel(cancelingCardId.value, { reason: cancelForm.value.reason })
    ElMessage.success('作废成功')
    cancelDialogVisible.value = false
    fetchCards()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '作废失败')
  } finally {
    submitting.value = false
  }
}

function getStatusType(status: number) {
  const map: Record<number, string> = { 0: 'info', 1: 'success', 2: 'warning', 3: 'danger' }
  return map[status] || 'info'
}

function getStatusText(status: number) {
  const map: Record<number, string> = { 0: '未激活', 1: '正常', 2: '已过期', 3: '已冻结' }
  return map[status] || '未知'
}

function getCardTypeText(type: string) {
  const map: Record<string, string> = { count: '次卡', period: '期卡', unlimited: '无限卡' }
  return map[type] || type
}

function formatDate(dateStr: string) {
  if (!dateStr) return '-'
  return dateStr
}

function getFrozenDuration(card: MembershipCard) {
  if (!card.frozen_at) return '-'
  const frozenAt = new Date(card.frozen_at).getTime()
  const now = Date.now()
  const diffMs = now - frozenAt
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24))
  return `${diffDays}天`
}

function getFrozenRemainingDays(card: MembershipCard) {
  if (!card.frozen_until) return '-'
  const frozenUntil = new Date(card.frozen_until).getTime()
  const now = Date.now()
  const diffMs = frozenUntil - now
  if (diffMs <= 0) return 0
  return Math.ceil(diffMs / (1000 * 60 * 60 * 24))
}

onMounted(() => {
  fetchCards()
  fetchUsers()
  fetchProducts()
})
</script>

<style scoped>
/* 续卡提示对话框样式 */
:deep(.renewal-dialog) {
  border-radius: 12px;
  overflow: hidden;
}

:deep(.renewal-dialog .el-dialog__header) {
  padding: 0;
  margin: 0;
}

:deep(.renewal-dialog .el-dialog__headerbtn) {
  top: 12px;
  right: 12px;
  font-size: 18px;
}

.renewal-content {
  padding: 4px 0;
}

.renewal-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.renewal-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.renewal-title {
  font-size: 14px;
  font-weight: 600;
  color: #E6A23C;
}

.renewal-subtitle {
  font-size: 13px;
  color: #606266;
  margin-bottom: 12px;
}

.renewal-rules {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 12px;
}

.rules-title {
  font-size: 13px;
  color: #E6A23C;
  font-weight: 500;
  margin-bottom: 8px;
}

.rules-item {
  font-size: 12px;
  color: #606266;
}

.rules-hint {
  font-size: 12px;
  color: #67C23A;
  margin-top: 6px;
}

.renewal-footer {
  font-size: 12px;
  color: #909399;
}
</style>