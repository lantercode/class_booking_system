<template>
  <div class="page-container">
    <div class="page-header">
      <h2>预约管理</h2>
    </div>

    <div class="filter-bar">
      <el-input
        v-model="keyword"
        placeholder="学员/排期筛选"
        style="width: 240px"
        clearable
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      >
        <template #suffix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-select
        v-model="statusFilter"
        placeholder="全部状态"
        style="width: 160px"
        clearable
        @change="handleSearch"
      >
        <el-option label="全部状态" value="" />
        <el-option v-for="opt in statusOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
      </el-select>
    </div>

    <div v-if="loadError" class="list-error-block">
      <el-result icon="error" title="加载预约列表失败" :sub-title="loadError">
        <template #extra>
          <el-button type="primary" @click="fetchBookings">重试</el-button>
        </template>
      </el-result>
    </div>

    <el-table
      v-else
      v-loading="loading"
      :data="bookings"
      stripe
      style="width: 100%"
      empty-text="暂无数据"
      :row-class-name="rowClassName"
    >
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column label="学员" min-width="130">
        <template #default="{ row }">
          <div class="student-cell">
            <span class="student-name">{{ row.student_nickname || `学员#${row.student_id}` }}</span>
            <span v-if="row.student_phone" class="student-phone">{{ row.student_phone }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="课程/排期" min-width="200">
        <template #default="{ row }">
          <div class="course-cell">
            <span class="course-name">{{ row.course_name || `课程#${row.schedule_id}` }}</span>
            <span class="course-time">{{ formatDateTimeRange(row.start_at, row.end_at) }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="130">
        <template #default="{ row }">
          <div class="status-cell">
            <el-tag :type="statusTagType(row)" size="small">
              {{ statusTagText(row) }}
            </el-tag>
            <span
              v-if="(row.status === 3 || row.status === 4 || row.display_status === 3 || row.display_status === 4) && row.checked_in_at"
              class="checked-in-time"
              :title="`签到时间：${formatDateTime(row.checked_in_at)}`"
            >
              签到 {{ formatShortDateTime(row.checked_in_at) }}
            </span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="会员卡" min-width="200">
        <template #default="{ row }">
          <div v-if="row.card_no" class="card-cell">
            <div class="card-main">
              <span class="card-no">{{ row.card_no }}</span>
              <el-tag :type="cardStatusTagType(row)" size="small" effect="light">
                {{ cardStatusTagText(row) }}
              </el-tag>
            </div>
          </div>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="来源" width="90">
        <template #default="{ row }">
          {{ sourceText(row.source) }}
        </template>
      </el-table-column>
      <el-table-column label="取消原因" min-width="120">
        <template #default="{ row }">
          {{ row.cancelled_reason || '—' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="row.status === 1"
            type="danger"
            size="small"
            text
            :loading="actionLoadingMap[row.id] === 'cancel'"
            @click="handleAdminCancel(row)"
          >
            代取消
          </el-button>
          <el-button
            v-if="row.status === 1"
            type="primary"
            size="small"
            text
            :loading="actionLoadingMap[row.id] === 'checkIn'"
            @click="handleCheckIn(row)"
          >
            签到
          </el-button>
          <el-button
            v-if="row.status === 3"
            type="primary"
            size="small"
            text
            :loading="actionLoadingMap[row.id] === 'complete'"
            @click="handleComplete(row)"
          >
            完成
          </el-button>
          <el-button
            v-if="[1, 3, 4].includes(row.status)"
            type="primary"
            size="small"
            text
            @click="goRollCall(row)"
          >
            点名
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrapper">
      <el-pagination
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="handlePageChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { bookingApi, type Booking } from '@dance-saas/api-client'
import { Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  cardStatusTagText,
  cardStatusTagType,
  formatDateTime,
  formatDateTimeRange,
  formatShortDateTime,
  rowCardInvalidClassName as rowClassName,
  sourceText,
  statusTagText,
  statusTagType,
} from './booking-display'

const router = useRouter()

const loading = ref(false)
const loadError = ref('')
const bookings = ref<Booking[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)

const keyword = ref('')
const statusFilter = ref<string | number>('')

const actionLoadingMap = reactive<Record<number, 'checkIn' | 'complete' | 'cancel' | undefined>>({})

const statusOptions = [
  { label: '已预约', value: 1 },
  { label: '已取消', value: 2 },
  { label: '已签到', value: 3 },
  { label: '已完成', value: 4 },
  { label: '未到场', value: 5 },
]

function goRollCall(row: Booking) {
  router.push(`/bookings/roll-call?schedule_id=${row.schedule_id}`)
}

async function fetchBookings() {
  loading.value = true
  loadError.value = ''
  try {
    const params: {
      page: number
      page_size: number
      status?: string
      keyword?: string
    } = {
      page: page.value,
      page_size: pageSize.value,
    }
    const kw = keyword.value.trim()
    if (kw) {
      params.keyword = kw
    }
    if (statusFilter.value !== '' && statusFilter.value !== null && statusFilter.value !== undefined) {
      params.status = String(statusFilter.value)
    }
    const res = await bookingApi.list(params)
    bookings.value = res.data.items
    total.value = res.data.total
  } catch (e: any) {
    loadError.value = e?.response?.data?.msg || '加载预约列表失败'
    ElMessage.error(loadError.value)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  fetchBookings()
}

function handlePageChange(p: number) {
  page.value = p
  fetchBookings()
}

function applyUpdated(row: Booking, updated: Booking) {
  row.status = updated.status
  if (updated.display_status !== undefined) {
    row.display_status = updated.display_status
  }
}

async function handleCheckIn(row: Booking) {
  actionLoadingMap[row.id] = 'checkIn'
  try {
    const res = await bookingApi.checkIn(row.id)
    applyUpdated(row, res.data)
    ElMessage.success('签到成功')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '签到失败')
  } finally {
    actionLoadingMap[row.id] = undefined
  }
}

async function handleComplete(row: Booking) {
  actionLoadingMap[row.id] = 'complete'
  try {
    const res = await bookingApi.complete(row.id)
    applyUpdated(row, res.data)
    ElMessage.success('已完成')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '操作失败')
  } finally {
    actionLoadingMap[row.id] = undefined
  }
}

async function handleAdminCancel(row: Booking) {
  try {
    const { value: reason } = await ElMessageBox.prompt('请输入取消原因（可选）', '代取消预约', {
      confirmButtonText: '确定取消',
      cancelButtonText: '再想想',
      inputPlaceholder: '如：学员临时有事',
      inputValidator: (val: string) => {
        if (val && val.length > 200) return '取消原因不能超过 200 字'
        return true
      },
    })
    actionLoadingMap[row.id] = 'cancel'
    try {
      const res = await bookingApi.adminCancel(row.id, reason || undefined)
      applyUpdated(row, res.data)
      ElMessage.success('预约已取消')
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.msg || '取消失败')
    } finally {
      actionLoadingMap[row.id] = undefined
    }
  } catch {
    // 用户取消了 prompt
  }
}

onMounted(() => {
  fetchBookings()
})
</script>

<style scoped>
.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
  flex-wrap: wrap;
}

.list-error-block {
  padding: 40px 0;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #ebeef5;
}

.pagination-wrapper {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.student-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.student-name {
  font-weight: normal;
}
.student-phone {
  font-size: 12px;
  color: #909399;
}

.course-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.course-name {
  font-weight: normal;
}
.course-time {
  font-size: 12px;
  color: #909399;
}

.status-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  align-items: flex-start;
}
.checked-in-time {
  font-size: 12px;
  color: #909399;
}

.card-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-start;
}
.card-main {
  display: flex;
  align-items: center;
  gap: 6px;
}
.card-no {
  font-family: monospace;
  font-size: 13px;
}

.muted {
  color: #c0c4cc;
}

:deep(.row-card-invalid) {
  background-color: #fdf6ec !important;
}
</style>
