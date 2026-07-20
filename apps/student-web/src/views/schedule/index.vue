<template>
  <div class="schedule-container">
    <header class="schedule-header">
      <el-button text @click="$router.back()">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
      <span class="header-title">{{ courseName }}</span>
      <div style="width: 60px"></div>
    </header>

    <div class="calendar-section">
      <div class="month-nav">
        <el-button text @click="prevMonth">
          <el-icon><ArrowLeft /></el-icon>
        </el-button>
        <span class="month-label">{{ monthLabel }}</span>
        <el-button text @click="nextMonth">
          <el-icon><ArrowRight /></el-icon>
        </el-button>
      </div>

      <div class="weekday-row">
        <span v-for="day in weekdays" :key="day" class="weekday-item">{{ day }}</span>
      </div>

      <div class="date-grid">
        <div
          v-for="(date, index) in calendarDates"
          :key="index"
          class="date-cell"
          :class="{
            'is-today': date.isToday,
            'is-selected': date.date === selectedDate,
            'is-other-month': !date.isCurrentMonth,
            'has-schedule': date.hasSchedule,
          }"
          @click="selectDate(date)"
        >
          <span class="date-num">{{ date.day }}</span>
          <span v-if="date.hasSchedule" class="schedule-dot"></span>
        </div>
      </div>
    </div>

    <div class="slots-section">
      <h3 v-if="selectedDate">{{ selectedDate }} 可约时段</h3>

      <div v-if="todaySlots.length === 0" class="empty-slots">
        <el-empty description="当天暂无排期" :image-size="80" />
      </div>

      <div v-else class="slot-list">
        <div
          v-for="slot in todaySlots"
          :key="slot.id"
          class="slot-card"
          :class="{ 'is-full': slot.status === 0 }"
        >
          <div class="slot-time">
            <span class="time-range">{{ slot.startTime }} - {{ slot.endTime }}</span>
            <el-tag :type="slot.status === 1 ? 'success' : 'danger'" size="small">
              {{ slot.status === 1 ? '可预约' : '已满' }}
            </el-tag>
          </div>
          <div class="slot-info">
            <span><el-icon><User /></el-icon> {{ slot.teacherName }}</span>
            <span><el-icon><Location /></el-icon> {{ slot.classroom }}</span>
            <span>
              <el-icon><Tickets /></el-icon>
              {{ slot.booked }} / {{ slot.capacity }}
            </span>
          </div>
          <div class="slot-action">
            <el-button
              type="primary"
              :disabled="slot.status !== 1"
              @click="handleBooking(slot)"
            >
              {{ slot.status === 1 ? '立即预约' : '已满' }}
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <el-dialog
      v-model="confirmVisible"
      title="确认预约"
      width="360px"
      :close-on-click-modal="false"
    >
      <div class="confirm-content" v-if="selectedSlot">
        <div class="confirm-item">
          <span class="label">时间</span>
          <span class="value">{{ selectedSlot.startTime }} - {{ selectedSlot.endTime }}</span>
        </div>
        <div class="confirm-item">
          <span class="label">教师</span>
          <span class="value">{{ selectedSlot.teacherName }}</span>
        </div>
        <div class="confirm-item">
          <span class="label">教室</span>
          <span class="value">{{ selectedSlot.classroom }}</span>
        </div>
      </div>
      <template #footer>
        <el-button @click="confirmVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmBooking" :loading="bookingLoading">确认预约</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft,
  ArrowRight,
  User,
  Location,
  Tickets,
} from '@element-plus/icons-vue'
import { scheduleApi, courseApi, bookingApi, type Schedule } from '@dance-saas/api-client'

const route = useRoute()
const courseId = Number(route.params.id)
const courseName = ref('课程排期')
const loading = ref(false)
const bookingLoading = ref(false)

const weekdays = ['日', '一', '二', '三', '四', '五', '六']

interface SlotView {
  id: number
  scheduleId: number
  startTime: string
  endTime: string
  teacherName: string
  classroom: string
  booked: number
  capacity: number
  status: number
}

interface CalendarDate {
  date: string
  day: number
  isToday: boolean
  isCurrentMonth: boolean
  hasSchedule: boolean
}

const currentDate = ref(new Date())
const selectedDate = ref('')
const allSchedules = ref<Schedule[]>([])
const confirmVisible = ref(false)
const selectedSlot = ref<SlotView | null>(null)

const todayStr = new Date().toISOString().slice(0, 10)

const monthLabel = computed(() => {
  const d = currentDate.value
  return `${d.getFullYear()}年${d.getMonth() + 1}月`
})

async function fetchCourse() {
  try {
    const res = await courseApi.getById(courseId)
    courseName.value = res.data.name
  } catch (_) {}
}

async function fetchSchedules() {
  loading.value = true
  try {
    const res = await scheduleApi.list({ course_id: courseId, page_size: 200, status: 1 })
    allSchedules.value = res.data.items
  } catch (_) {} finally {
    loading.value = false
  }
}

function hasScheduleOnDate(date: string): boolean {
  return allSchedules.value.some((s) => s.start_at.slice(0, 10) === date)
}

const calendarDates = computed(() => {
  const year = currentDate.value.getFullYear()
  const month = currentDate.value.getMonth()
  const firstDay = new Date(year, month, 1)
  const lastDay = new Date(year, month + 1, 0)
  const startDayOfWeek = firstDay.getDay()

  const dates: CalendarDate[] = []

  for (let i = startDayOfWeek - 1; i >= 0; i--) {
    const d = new Date(year, month, -i)
    dates.push({
      date: d.toISOString().slice(0, 10),
      day: d.getDate(),
      isToday: d.toISOString().slice(0, 10) === todayStr,
      isCurrentMonth: false,
      hasSchedule: hasScheduleOnDate(d.toISOString().slice(0, 10)),
    })
  }

  for (let i = 1; i <= lastDay.getDate(); i++) {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(i).padStart(2, '0')}`
    dates.push({
      date: dateStr,
      day: i,
      isToday: dateStr === todayStr,
      isCurrentMonth: true,
      hasSchedule: hasScheduleOnDate(dateStr),
    })
  }

  const remaining = 42 - dates.length
  for (let i = 1; i <= remaining; i++) {
    const d = new Date(year, month + 1, i)
    dates.push({
      date: d.toISOString().slice(0, 10),
      day: d.getDate(),
      isToday: d.toISOString().slice(0, 10) === todayStr,
      isCurrentMonth: false,
      hasSchedule: hasScheduleOnDate(d.toISOString().slice(0, 10)),
    })
  }

  return dates
})

const todaySlots = computed(() => {
  if (!selectedDate.value) return []
  return allSchedules.value
    .filter((s) => s.start_at.slice(0, 10) === selectedDate.value)
    .map((s): SlotView => ({
      id: s.id,
      scheduleId: s.id,
      startTime: new Date(s.start_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      endTime: new Date(s.end_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      teacherName: `教师#${s.teacher_id}`,
      classroom: s.classroom_id ? `教室#${s.classroom_id}` : '未指定',
      booked: s.booked_count,
      capacity: s.capacity,
      status: s.booked_count >= s.capacity ? 0 : 1,
    }))
})

function selectDate(date: CalendarDate) {
  if (!date.isCurrentMonth) return
  selectedDate.value = date.date
}

function prevMonth() {
  const d = new Date(currentDate.value)
  d.setMonth(d.getMonth() - 1)
  currentDate.value = d
}

function nextMonth() {
  const d = new Date(currentDate.value)
  d.setMonth(d.getMonth() + 1)
  currentDate.value = d
}

function handleBooking(slot: SlotView) {
  selectedSlot.value = slot
  confirmVisible.value = true
}

async function confirmBooking() {
  if (!selectedSlot.value) return
  bookingLoading.value = true
  try {
    await bookingApi.create({ schedule_id: selectedSlot.value.scheduleId })
    ElMessage.success('预约成功')
    confirmVisible.value = false
    selectedSlot.value = null
    fetchSchedules()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '预约失败')
  } finally {
    bookingLoading.value = false
  }
}

onMounted(() => {
  fetchCourse()
  fetchSchedules()
  selectedDate.value = todayStr
})
</script>

<style scoped lang="scss">
.schedule-container {
  min-height: 100vh;
  background: #f5f7fa;
  max-width: 800px;
  margin: 0 auto;
}

.schedule-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);

  .header-title {
    font-size: 16px;
    font-weight: 600;
    color: #303133;
  }
}

.calendar-section {
  background: #fff;
  margin: 16px;
  border-radius: 12px;
  padding: 16px;

  .month-nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    .month-label {
      font-size: 16px;
      font-weight: 600;
      color: #303133;
    }
  }

  .weekday-row {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    text-align: center;
    margin-bottom: 8px;

    .weekday-item {
      font-size: 12px;
      color: #909399;
      padding: 4px 0;
    }
  }

  .date-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 4px;
  }

  .date-cell {
    aspect-ratio: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.2s;
    position: relative;

    &:hover { background: #f0f2f5; }

    &.is-other-month {
      opacity: 0.3;
      cursor: default;
    }

    &.is-today {
      background: #ecf5ff;
      .date-num { color: #667eea; font-weight: 700; }
    }

    &.is-selected {
      background: #667eea;
      .date-num { color: #fff; font-weight: 700; }
    }

    &.has-schedule {
      .schedule-dot {
        width: 5px;
        height: 5px;
        border-radius: 50%;
        background: #f56c6c;
        position: absolute;
        bottom: 4px;
      }
    }

    .date-num {
      font-size: 14px;
      color: #303133;
    }
  }
}

.slots-section {
  margin: 0 16px 16px;
  padding: 16px;
  background: #fff;
  border-radius: 12px;

  h3 {
    font-size: 15px;
    color: #303133;
    margin-bottom: 12px;
  }

  .slot-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .slot-card {
    border: 1px solid #ebeef5;
    border-radius: 10px;
    padding: 14px;
    transition: border-color 0.2s;

    &:hover { border-color: #667eea; }

    &.is-full {
      opacity: 0.6;
      background: #fafafa;
    }

    .slot-time {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;

      .time-range {
        font-size: 15px;
        font-weight: 600;
        color: #303133;
      }
    }

    .slot-info {
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      margin-bottom: 12px;

      span {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 13px;
        color: #606266;
      }
    }

    .slot-action {
      text-align: right;
    }
  }
}

.confirm-content {
  .confirm-item {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid #f0f0f0;

    .label { color: #909399; font-size: 14px; }
    .value { color: #303133; font-size: 14px; font-weight: 500; }
  }
}
</style>