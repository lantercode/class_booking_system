<template>
  <div class="schedule-container">
    <header class="page-header">
      <el-button text @click="$router.push('/courses')">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
      <span class="header-title">排期管理</span>
      <div style="width: 60px"></div>
    </header>

    <div class="filter-bar">
      <el-select v-model="selectedCourseId" placeholder="选择课程" class="course-select" @change="onCourseChange">
        <el-option v-for="c in courses" :key="c.id" :label="c.name" :value="c.id" />
      </el-select>
      <el-button type="primary" class="batch-btn" @click="showBatchDialog = true" :disabled="!selectedCourseId">
        <el-icon><Plus /></el-icon>
        批量排期
      </el-button>
    </div>

    <div class="calendar-card">
      <div class="month-nav">
        <el-button text :icon="ArrowLeft" @click="prevMonth" />
        <span class="month-label">{{ currentYear }}年{{ currentMonth + 1 }}月</span>
        <el-button text :icon="ArrowRight" @click="nextMonth" />
      </div>

      <div class="weekday-row">
        <span v-for="d in weekdays" :key="d" class="weekday">{{ d }}</span>
      </div>

      <div class="calendar-grid">
        <div
          v-for="(cell, i) in calendarCells"
          :key="i"
          class="calendar-cell"
          :class="{
            'is-other-month': !cell.isCurrentMonth,
            'is-today': cell.isToday,
            'has-schedule': cell.hasSchedule,
          }"
          @click="selectDate(cell)"
        >
          <span class="cell-date">{{ cell.day }}</span>
          <span v-if="cell.hasSchedule" class="cell-dot"></span>
        </div>
      </div>
    </div>

    <div v-if="selectedDate" class="schedule-list">
      <div class="list-header">
        <span class="list-title">{{ selectedDate }} 排期</span>
        <el-button text type="primary" @click="showAddDialog" :disabled="!selectedCourseId">
          <el-icon><Plus /></el-icon>
          添加时段
        </el-button>
      </div>

      <div v-if="dateSchedules.length === 0" class="empty-state">
        <el-empty description="当天暂无排期" :image-size="80" />
      </div>

      <div v-else class="slot-list">
        <div v-for="s in dateSchedules" :key="s.id" class="slot-item">
          <div class="slot-left">
            <el-icon><Clock /></el-icon>
            <span class="time-text">{{ formatTime(s.start_at) }} - {{ formatTime(s.end_at) }}</span>
          </div>
          <div class="slot-right">
            <span class="booking-info">{{ s.booked_count }}/{{ s.capacity }}</span>
            <el-button type="primary" text size="small" @click="viewStudents(s.id)">学员</el-button>
            <el-button type="danger" text size="small" @click="handleDelete(s)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <el-dialog v-model="showAddDialog" title="添加时段" width="360px">
      <el-form label-position="top">
        <el-form-item label="开始时间">
          <el-time-picker v-model="addForm.startTime" format="HH:mm" value-format="HH:mm" style="width:100%" />
        </el-form-item>
        <el-form-item label="结束时间">
          <el-time-picker v-model="addForm.endTime" format="HH:mm" value-format="HH:mm" style="width:100%" />
        </el-form-item>
        <el-form-item label="容量">
          <el-input-number v-model="addForm.capacity" :min="1" :max="200" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="handleAddSlot" :loading="adding">添加</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showBatchDialog" title="批量排期" width="90%" :close-on-click-modal="false">
      <el-form label-position="top">
        <el-form-item label="生成范围">
          <el-radio-group v-model="batchWeeks">
            <el-radio-button :value="1">1周</el-radio-button>
            <el-radio-button :value="2">2周</el-radio-button>
            <el-radio-button :value="4">4周</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="上课时段">
          <el-checkbox-group v-model="batchTimes">
            <el-checkbox v-for="t in timeOptions" :key="t" :value="t" :label="t" />
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="容量">
          <el-input-number v-model="batchCapacity" :min="1" :max="200" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBatchDialog = false">取消</el-button>
        <el-button type="primary" @click="generateBatch" :loading="batchGenerating">生成排期</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft, ArrowRight, Plus, Clock, Delete,
} from '@element-plus/icons-vue'
import { scheduleApi, courseApi, type Schedule } from '@dance-saas/api-client'

const router = useRouter()
const weekdays = ['日', '一', '二', '三', '四', '五', '六']

const courses = ref<{ id: number; name: string }[]>([])
const selectedCourseId = ref<number | null>(null)
const allSchedules = ref<Schedule[]>([])
const loading = ref(false)
const adding = ref(false)
const batchGenerating = ref(false)

const currentYear = ref(new Date().getFullYear())
const currentMonth = ref(new Date().getMonth())
const selectedDate = ref<string | null>(null)

const showAddDialog = ref(false)
const showBatchDialog = ref(false)
const addForm = ref({ startTime: '09:00', endTime: '10:00', capacity: 15 })

const batchWeeks = ref(2)
const batchTimes = ref(['09:00', '10:30', '14:00', '15:30'])
const batchCapacity = ref(15)
const timeOptions = ['09:00', '10:30', '14:00', '15:30', '17:00']

async function fetchCourses() {
  try {
    const res = await courseApi.list({ page_size: 200 })
    courses.value = res.data.items
    if (courses.value.length > 0) {
      selectedCourseId.value = courses.value[0].id
      fetchSchedules()
    }
  } catch (_) {}
}

async function fetchSchedules() {
  if (!selectedCourseId.value) return
  loading.value = true
  try {
    const res = await scheduleApi.list({
      course_id: selectedCourseId.value,
      page_size: 500,
      status: 1,
    })
    allSchedules.value = res.data.items
  } catch (_) {} finally {
    loading.value = false
  }
}

function onCourseChange() {
  selectedDate.value = null
  fetchSchedules()
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const calendarCells = computed(() => {
  const year = currentYear.value
  const month = currentMonth.value
  const firstDay = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const today = new Date()
  const todayStr = today.toISOString().split('T')[0]

  const scheduleDates = new Set(allSchedules.value.map((s) => s.start_at.slice(0, 10)))

  const cells: { day: number; isCurrentMonth: boolean; isToday: boolean; hasSchedule: boolean; dateStr: string }[] = []

  const prevMonthDays = new Date(year, month, 0).getDate()
  for (let i = firstDay - 1; i >= 0; i--) {
    const d = prevMonthDays - i
    const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    cells.push({ day: d, isCurrentMonth: false, isToday: false, hasSchedule: scheduleDates.has(dateStr), dateStr })
  }

  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    cells.push({ day: d, isCurrentMonth: true, isToday: dateStr === todayStr, hasSchedule: scheduleDates.has(dateStr), dateStr })
  }

  const remaining = 42 - cells.length
  for (let d = 1; d <= remaining; d++) {
    const dateStr = `${year}-${String(month + 2).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    cells.push({ day: d, isCurrentMonth: false, isToday: false, hasSchedule: scheduleDates.has(dateStr), dateStr })
  }

  return cells
})

const dateSchedules = computed(() => {
  if (!selectedDate.value) return []
  return allSchedules.value.filter((s) => s.start_at.slice(0, 10) === selectedDate.value)
})

function prevMonth() {
  if (currentMonth.value === 0) { currentMonth.value = 11; currentYear.value-- }
  else { currentMonth.value-- }
}

function nextMonth() {
  if (currentMonth.value === 11) { currentMonth.value = 0; currentYear.value++ }
  else { currentMonth.value++ }
}

function selectDate(cell: { isCurrentMonth: boolean; dateStr: string }) {
  if (!cell.isCurrentMonth) return
  selectedDate.value = cell.dateStr
}

function viewStudents(scheduleId: number) {
  router.push(`/students/${scheduleId}`)
}

async function handleDelete(schedule: Schedule) {
  try {
    await ElMessageBox.confirm('确定要删除此排期吗？', '确认', { type: 'warning' })
    await scheduleApi.cancel(schedule.id)
    ElMessage.success('排期已取消')
    fetchSchedules()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e?.response?.data?.msg || '操作失败')
  }
}

async function handleAddSlot() {
  if (!selectedDate.value || !selectedCourseId.value) return
  adding.value = true
  try {
    const [sh, sm] = addForm.value.startTime.split(':').map(Number)
    const [eh, em] = addForm.value.endTime.split(':').map(Number)
    const year = currentYear.value
    const month = currentMonth.value
    const day = Number(selectedDate.value.split('-')[2])
    const startAt = new Date(year, month, day, sh, sm).toISOString()
    const endAt = new Date(year, month, day, eh, em).toISOString()

    await scheduleApi.create({
      course_id: selectedCourseId.value,
      teacher_id: 0,
      start_at: startAt,
      end_at: endAt,
      capacity: addForm.value.capacity,
    })
    ElMessage.success('时段已添加')
    showAddDialog.value = false
    fetchSchedules()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '添加失败')
  } finally {
    adding.value = false
  }
}

async function generateBatch() {
  if (!selectedCourseId.value || batchTimes.value.length === 0) return
  batchGenerating.value = true
  let created = 0
  try {
    const today = new Date(currentYear.value, currentMonth.value, 1)
    for (let d = 0; d < batchWeeks.value * 7; d++) {
      const date = new Date(today)
      date.setDate(date.getDate() + d)
      if (date.getDay() === 0 || date.getDay() === 6) continue
      const dateStr = date.toISOString().slice(0, 10)

      for (const startTime of batchTimes.value) {
        const [h, m] = startTime.split(':').map(Number)
        const [eh, em] = [(h + 1) % 24, m]
        const startAt = new Date(date.getFullYear(), date.getMonth(), date.getDate(), h, m).toISOString()
        const endAt = new Date(date.getFullYear(), date.getMonth(), date.getDate(), eh, em).toISOString()

        try {
          await scheduleApi.create({
            course_id: selectedCourseId.value,
            teacher_id: 0,
            start_at: startAt,
            end_at: endAt,
            capacity: batchCapacity.value,
          })
          created++
        } catch (_) {}
      }
    }
    showBatchDialog.value = false
    ElMessage.success(`已生成 ${created} 条排期`)
    fetchSchedules()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '批量生成失败')
  } finally {
    batchGenerating.value = false
  }
}

onMounted(() => {
  fetchCourses()
})
</script>

<style scoped lang="scss">
.schedule-container {
  min-height: 100vh;
  background: linear-gradient(180deg, #fef5f9 0%, #f0f2ff 30%, #f5f7fa 100%);
  max-width: 800px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.04);
  position: sticky;
  top: 0;
  z-index: 50;

  .header-title {
    font-size: 17px;
    font-weight: 700;
    color: #1a1a2e;
  }
}

.filter-bar {
  display: flex;
  gap: 12px;
  padding: 16px;
  align-items: center;

  .course-select { flex: 1; }

  .batch-btn {
    border-radius: 14px;
    font-weight: 600;
    background: linear-gradient(135deg, #667eea, #764ba2);
    border: none;
    flex-shrink: 0;
  }
}

.calendar-card {
  background: #fff;
  margin: 0 16px;
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);

  .month-nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    .month-label {
      font-size: 16px;
      font-weight: 700;
      color: #1a1a2e;
    }
  }

  .weekday-row {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    text-align: center;
    margin-bottom: 8px;

    .weekday {
      font-size: 12px;
      color: #909399;
      font-weight: 600;
      padding: 4px;
    }
  }

  .calendar-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 2px;
  }

  .calendar-cell {
    aspect-ratio: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    border-radius: 10px;
    cursor: pointer;
    transition: background 0.2s;
    position: relative;

    &:hover { background: #f0f2ff; }

    &.is-other-month {
      opacity: 0.3;
      cursor: default;
    }

    &.is-today {
      background: #667eea;
      .cell-date { color: #fff; font-weight: 700; }
    }

    &.has-schedule .cell-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #667eea;
      margin-top: 2px;
    }

    &.is-today.has-schedule .cell-dot { background: #67c23a; }

    .cell-date {
      font-size: 14px;
      color: #303133;
    }
  }
}

.schedule-list {
  margin: 16px;
  background: #fff;
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);

  .list-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    .list-title {
      font-size: 15px;
      font-weight: 700;
      color: #1a1a2e;
    }
  }

  .slot-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .slot-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px;
    background: #f8f9fc;
    border-radius: 10px;

    .slot-left {
      display: flex;
      align-items: center;
      gap: 8px;

      .time-text {
        font-size: 14px;
        font-weight: 600;
        color: #303133;
      }
    }

    .slot-right {
      display: flex;
      align-items: center;
      gap: 8px;

      .booking-info {
        font-size: 13px;
        color: #909399;
      }
    }
  }
}

.empty-state {
  padding: 20px 0;
}
</style>