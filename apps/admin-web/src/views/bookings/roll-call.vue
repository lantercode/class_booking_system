<template>
  <div class="page-container">
    <div class="page-header roll-call-header">
      <h2>排期签到点名</h2>
      <el-button @click="router.push('/bookings')">返回预约列表</el-button>
    </div>

    <div class="filter-bar">
      <el-select
        v-model="selectedScheduleId"
        filterable
        remote
        clearable
        reserve-keyword
        placeholder="搜索课程名称选择排期"
        :remote-method="searchSchedules"
        :loading="scheduleLoading"
        popper-class="roll-call-schedule-popper"
        style="width: 440px"
        @change="handleScheduleChange"
      >
        <el-option
          v-for="s in scheduleOptions"
          :key="s.id"
          :label="scheduleOptionLabel(s)"
          :value="s.id"
        >
          <div class="schedule-option">
            <span class="option-course">{{ s.course_name || `课程#${s.course_id}` }}</span>
            <span class="option-meta">
              {{ formatDateTime(s.start_at) }} · {{ s.teacher_name || '教师待定' }}
            </span>
          </div>
        </el-option>
      </el-select>
    </div>

    <!-- 未选择排期：引导态 -->
    <div v-if="!selectedScheduleId" class="guide-block">
      <el-empty description="请选择排期查看签到名单" />
    </div>

    <!-- 加载失败：错误态 -->
    <div v-else-if="loadError" class="list-error-block">
      <el-result icon="error" title="加载签到名单失败" :sub-title="loadError">
        <template #extra>
          <el-button type="primary" @click="fetchBookings">重试</el-button>
        </template>
      </el-result>
    </div>

    <!-- 数据态（空数据由表格 empty-text 呈现） -->
    <template v-else>
      <el-table
        v-loading="loading"
        :data="bookings"
        stripe
        style="width: 100%"
        empty-text="暂无预约"
        :row-class-name="rowClassName"
      >
        <el-table-column type="index" label="序号" width="60" />
        <el-table-column label="学员" min-width="150">
          <template #default="{ row }">
            <div class="student-cell">
              <span class="student-name">{{ row.student_nickname || `学员#${row.student_id}` }}</span>
              <span v-if="row.student_phone" class="student-phone">{{ row.student_phone }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="预约状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row)" size="small">
              {{ statusTagText(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="计划卡" min-width="170">
          <template #default="{ row }">
            <div v-if="row.card_no" class="card-cell">
              <span class="card-no">{{ row.card_no }}</span>
              <el-tag :type="cardStatusTagType(row)" size="small" effect="light">
                {{ cardStatusTagText(row) }}
              </el-tag>
            </div>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="签到时间" width="150">
          <template #default="{ row }">
            {{ row.checked_in_at ? formatDateTime(row.checked_in_at) : '—' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 1"
              type="primary"
              size="small"
              text
              :loading="actionLoadingMap[row.id] === 'checkIn'"
              @click="handleCheckIn(row)"
            >
              代签到
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
    </template>
  </div>
</template>

<script setup lang="ts">
import { bookingApi, scheduleApi, type Booking, type Schedule } from '@dance-saas/api-client'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  cardAbnormalStatusText,
  cardStatusTagText,
  cardStatusTagType,
  formatDateTime,
  rowCardInvalidClassName as rowClassName,
  statusTagText,
  statusTagType,
} from './booking-display'

const route = useRoute()
const router = useRouter()

// 排期选择器
const selectedScheduleId = ref<number | null>(null)
const scheduleOptions = ref<Schedule[]>([])
const scheduleLoading = ref(false)

// 名单
const loading = ref(false)
const loadError = ref('')
const bookings = ref<Booking[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)

const actionLoadingMap = reactive<Record<number, 'checkIn' | 'complete' | undefined>>({})

function scheduleOptionLabel(s: Schedule): string {
  const course = s.course_name || `课程#${s.course_id}`
  return `${course} ${formatDateTime(s.start_at)}`
}

async function searchSchedules(query: string) {
  scheduleLoading.value = true
  try {
    const kw = query.trim()
    const res = await scheduleApi.list({
      page: 1,
      page_size: 20,
      ...(kw ? { course_name: kw } : {}),
    })
    scheduleOptions.value = res.data.items
  } catch (e: any) {
    // 远程搜索失败静默保留现有选项，避免打断选择流程
    console.error('搜索排期失败', e?.response?.data?.msg || e)
  } finally {
    scheduleLoading.value = false
  }
}

function handleScheduleChange(id: number | null) {
  if (!id) {
    bookings.value = []
    total.value = 0
    page.value = 1
    loadError.value = ''
    return
  }
  page.value = 1
  fetchBookings()
}

async function fetchBookings() {
  if (!selectedScheduleId.value) return
  loading.value = true
  loadError.value = ''
  try {
    const res = await bookingApi.list({
      schedule_id: selectedScheduleId.value,
      page: page.value,
      page_size: pageSize.value,
    })
    bookings.value = res.data.items
    total.value = res.data.total
  } catch (e: any) {
    loadError.value = e?.response?.data?.msg || '加载签到名单失败'
    ElMessage.error(loadError.value)
  } finally {
    loading.value = false
  }
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
  if (updated.checked_in_at !== undefined) {
    row.checked_in_at = updated.checked_in_at
  }
  if (updated.card_status !== undefined) {
    row.card_status = updated.card_status
  }
  if (updated.remaining_credits !== undefined) {
    row.remaining_credits = updated.remaining_credits
  }
}

async function handleCheckIn(row: Booking) {
  const studentName = row.student_nickname || `学员#${row.student_id}`
  const abnormal = cardAbnormalStatusText(row.card_status)
  const message = abnormal
    ? `确认为学员「${studentName}」代签到？该学员计划卡状态异常（${abnormal}），签到可能被拒绝。`
    : `确认为学员「${studentName}」代签到？`
  try {
    await ElMessageBox.confirm(message, '代签到确认', {
      confirmButtonText: '确认签到',
      cancelButtonText: '取消',
      type: abnormal ? 'warning' : 'info',
    })
  } catch {
    return
  }
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
  const studentName = row.student_nickname || `学员#${row.student_id}`
  try {
    await ElMessageBox.confirm(`确认为学员「${studentName}」标记完成？`, '完成确认', {
      confirmButtonText: '确认完成',
      cancelButtonText: '取消',
      type: 'info',
    })
  } catch {
    return
  }
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

onMounted(async () => {
  await searchSchedules('')
  const qid = Number(route.query.schedule_id)
  if (qid && Number.isFinite(qid) && qid > 0) {
    try {
      const res = await scheduleApi.getById(qid)
      scheduleOptions.value = [res.data, ...scheduleOptions.value.filter(s => s.id !== qid)]
      selectedScheduleId.value = qid
      await fetchBookings()
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.msg || '未找到指定排期，请重新选择')
    }
  }
})
</script>

<style scoped>
.roll-call-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
  flex-wrap: wrap;
}

.schedule-option {
  display: flex;
  flex-direction: column;
  gap: 2px;
  line-height: 1.4;
}
.option-course {
  font-size: 14px;
}
.option-meta {
  font-size: 12px;
  color: #909399;
}

.guide-block {
  padding: 40px 0;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #ebeef5;
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

.card-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-start;
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

<!-- 排期下拉 popper 挂载在 body 下（teleport），需用非 scoped 样式覆盖单行选项高度，避免两行内容被裁切 -->
<style>
.el-popper.roll-call-schedule-popper .el-select-dropdown__item {
  height: auto;
  line-height: 1.45;
  padding-top: 7px;
  padding-bottom: 7px;
  white-space: normal;
}
</style>
