<template>
  <view class="page">
    <view class="calendar-header">
      <view class="nav-btn" @click="prevWeek">
        <text>←</text>
      </view>
      <view class="week-title">
        <text>{{ weekTitle }}</text>
      </view>
      <view class="nav-btn" @click="nextWeek">
        <text>→</text>
      </view>
    </view>

    <view class="week-days">
      <view 
        class="day-item" 
        v-for="(day, index) in weekDays" 
        :key="index"
        :class="{ active: isToday(day), selected: selectedDay === day.dateStr }"
        @click="selectDay(day.dateStr)"
      >
        <text class="day-name">{{ day.name }}</text>
        <text class="day-num">{{ day.num }}</text>
      </view>
    </view>

    <view class="schedule-container">
      <view class="schedule-header">
        <text class="time-label">时间</text>
        <text class="course-label">课程安排</text>
      </view>
      
      <view class="schedule-grid">
        <view class="time-column">
          <view class="time-slot" v-for="time in timeSlots" :key="time">
            <text>{{ time }}</text>
          </view>
        </view>
        
        <view class="schedule-column">
          <view 
            class="schedule-block" 
            v-for="schedule in daySchedules" 
            :key="schedule.id"
            @click="handleScheduleClick(schedule)"
          >
            <text class="block-course">{{ schedule.course_name }}</text>
            <text class="block-teacher">{{ schedule.teacher_name }}</text>
            <text class="block-time">{{ formatScheduleTime(schedule) }}</text>
            <view class="block-status" :class="getStatusClass(schedule)">
              <text>{{ getStatusText(schedule) }}</text>
            </view>
          </view>
          
          <view class="empty-hint" v-if="daySchedules.length === 0">
            <text>当天暂无排期</text>
          </view>
        </view>
      </view>
    </view>

    <view class="section" v-if="showDetail">
      <view class="detail-card">
        <view class="detail-header">
          <text class="detail-title">{{ selectedSchedule?.course_name }}</text>
          <view class="close-btn" @click="showDetail = false">
            <text>✕</text>
          </view>
        </view>
        <view class="detail-info">
          <view class="info-row">
            <text class="info-icon">📅</text>
            <text class="info-text">{{ formatDetailDate(selectedSchedule?.start_at) }}</text>
          </view>
          <view class="info-row">
            <text class="info-icon">⏱️</text>
            <text class="info-text">{{ formatDetailTime(selectedSchedule?.start_at) }} - {{ formatDetailTime(selectedSchedule?.end_at) }}</text>
          </view>
          <view class="info-row">
            <text class="info-icon">👨‍🏫</text>
            <text class="info-text">{{ selectedSchedule?.teacher_name }}</text>
          </view>
          <view class="info-row">
            <text class="info-icon">🏠</text>
            <text class="info-text">{{ selectedSchedule?.classroom_name }}</text>
          </view>
          <view class="info-row">
            <text class="info-icon">👥</text>
            <text class="info-text">已预约 {{ selectedSchedule?.booked_count }} / {{ selectedSchedule?.capacity }} 人</text>
          </view>
        </view>
        <view class="detail-action">
          <view 
            class="action-btn" 
            v-if="canBook(selectedSchedule)"
            @click="handleBooking"
          >
            <text>立即预约</text>
          </view>
          <view class="action-btn disabled" v-else>
            <text>{{ selectedSchedule?.booked_count >= selectedSchedule?.capacity ? '已满' : '已预约' }}</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { scheduleApi, bookingApi } from '@/api'

const currentWeekStart = ref(getWeekStart(new Date()))
const selectedDay = ref('')
const schedules = ref<any[]>([])
const showDetail = ref(false)
const selectedSchedule = ref<any>(null)

const timeSlots = ['08:00', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00', '18:00', '19:00', '20:00', '21:00']

onMounted(() => {
  selectedDay.value = formatDateStr(new Date())
  loadSchedules()
})

function getWeekStart(date: Date) {
  const d = new Date(date)
  const day = d.getDay()
  const diff = d.getDate() - day + (day === 0 ? -6 : 1)
  return new Date(d.setDate(diff))
}

function formatDateStr(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

const weekDays = computed(() => {
  const days = []
  const dayNames = ['一', '二', '三', '四', '五', '六', '日']
  for (let i = 0; i < 7; i++) {
    const date = new Date(currentWeekStart.value)
    date.setDate(date.getDate() + i)
    days.push({
      name: dayNames[i],
      num: date.getDate(),
      dateStr: formatDateStr(date),
      date: date
    })
  }
  return days
})

const weekTitle = computed(() => {
  const start = currentWeekStart.value
  const end = new Date(start)
  end.setDate(end.getDate() + 6)
  return `${start.getMonth() + 1}月${start.getDate()}日 - ${end.getMonth() + 1}月${end.getDate()}日`
})

const daySchedules = computed(() => {
  return schedules.value.filter(s => s.start_at?.startsWith(selectedDay.value))
})

function prevWeek() {
  const newStart = new Date(currentWeekStart.value)
  newStart.setDate(newStart.getDate() - 7)
  currentWeekStart.value = newStart
  loadSchedules()
}

function nextWeek() {
  const newStart = new Date(currentWeekStart.value)
  newStart.setDate(newStart.getDate() + 7)
  currentWeekStart.value = newStart
  loadSchedules()
}

function selectDay(dateStr: string) {
  selectedDay.value = dateStr
}

function isToday(day: any) {
  const today = formatDateStr(new Date())
  return day.dateStr === today
}

async function loadSchedules() {
  try {
    const res = await scheduleApi.list({ page_size: 100 })
    schedules.value = res.data.items || []
  } catch (e) {
    console.error('加载排期失败', e)
  }
}

function formatScheduleTime(schedule: any) {
  if (!schedule.start_at) return ''
  const start = new Date(schedule.start_at)
  const end = new Date(schedule.end_at)
  return `${start.getHours()}:${String(start.getMinutes()).padStart(2, '0')}-${end.getHours()}:${String(end.getMinutes()).padStart(2, '0')}`
}

function getStatusClass(schedule: any) {
  const now = new Date()
  const start = new Date(schedule.start_at)
  const end = new Date(schedule.end_at)
  
  if (schedule.booked_count >= schedule.capacity) return 'status-full'
  if (now > end) return 'status-ended'
  if (now >= start && now <= end) return 'status-ongoing'
  return 'status-upcoming'
}

function getStatusText(schedule: any) {
  const now = new Date()
  const start = new Date(schedule.start_at)
  const end = new Date(schedule.end_at)
  
  if (schedule.booked_count >= schedule.capacity) return '已满'
  if (now > end) return '已结束'
  if (now >= start && now <= end) return '进行中'
  return `${schedule.booked_count}/${schedule.capacity}`
}

function handleScheduleClick(schedule: any) {
  selectedSchedule.value = schedule
  showDetail.value = true
}

function formatDetailDate(dateStr: string) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日 星期${['日', '一', '二', '三', '四', '五', '六'][date.getDay()]}`
}

function formatDetailTime(dateStr: string) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
}

function canBook(schedule: any) {
  if (!schedule) return false
  if (schedule.booked_count >= schedule.capacity) return false
  const now = new Date()
  const start = new Date(schedule.start_at)
  return now < start
}

async function handleBooking() {
  if (!selectedSchedule.value) return
  
  try {
    await bookingApi.create({ schedule_id: selectedSchedule.value.id })
    uni.showToast({ title: '预约成功', icon: 'success' })
    selectedSchedule.value.booked_count++
    showDetail.value = false
  } catch (e: any) {
    uni.showToast({ title: e?.response?.data?.msg || '预约失败', icon: 'none' })
  }
}
</script>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 120rpx;
}

.calendar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 30rpx;
  background: #fff;
}

.nav-btn {
  width: 60rpx;
  height: 60rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f5f5;
  border-radius: 50%;
  font-size: 32rpx;
  color: #666;
}

.week-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #333;
}

.week-days {
  display: flex;
  background: #fff;
  padding: 0 30rpx 30rpx;
  gap: 10rpx;
}

.day-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20rpx 0;
  border-radius: 16rpx;
  background: #f5f5f5;
  
  &.active {
    background: #e8f5e9;
    .day-num {
      background: #4caf50;
      color: #fff;
    }
  }
  
  &.selected {
    background: #e3f2fd;
    .day-num {
      background: #1989fa;
      color: #fff;
    }
  }
}

.day-name {
  font-size: 24rpx;
  color: #999;
  margin-bottom: 12rpx;
}

.day-num {
  width: 56rpx;
  height: 56rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 28rpx;
  color: #333;
}

.schedule-container {
  margin: 30rpx;
  background: #fff;
  border-radius: 20rpx;
  overflow: hidden;
}

.schedule-header {
  display: flex;
  padding: 20rpx 30rpx;
  border-bottom: 2rpx solid #f5f5f5;
}

.time-label {
  width: 120rpx;
  font-size: 26rpx;
  color: #999;
}

.course-label {
  flex: 1;
  font-size: 26rpx;
  color: #333;
  font-weight: bold;
}

.schedule-grid {
  display: flex;
}

.time-column {
  width: 120rpx;
  padding: 20rpx 0;
  border-right: 2rpx solid #f5f5f5;
}

.time-slot {
  height: 100rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22rpx;
  color: #999;
}

.schedule-column {
  flex: 1;
  padding: 20rpx;
}

.schedule-block {
  background: #e3f2fd;
  border-radius: 16rpx;
  padding: 20rpx;
  margin-bottom: 20rpx;
}

.block-course {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
  display: block;
}

.block-teacher {
  font-size: 24rpx;
  color: #666;
  margin-top: 8rpx;
  display: block;
}

.block-time {
  font-size: 24rpx;
  color: #1989fa;
  margin-top: 8rpx;
  display: block;
}

.block-status {
  display: inline-block;
  padding: 8rpx 16rpx;
  border-radius: 116rpx;
  font-size: 22rpx;
  margin-top: 12rpx;
}

.status-full {
  background: #ffebee;
  color: #f44336;
}

.status-ended {
  background: #f5f5f5;
  color: #999;
}

.status-ongoing {
  background: #e8f5e9;
  color: #4caf50;
}

.status-upcoming {
  background: #fff3e0;
  color: #ff9800;
}

.empty-hint {
  text-align: center;
  padding: 100rpx 0;
  color: #999;
  font-size: 28rpx;
}

.section {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 30rpx;
}

.detail-card {
  width: 100%;
  background: #fff;
  border-radius: 20rpx;
  overflow: hidden;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 30rpx;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.detail-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #fff;
}

.close-btn {
  width: 48rpx;
  height: 48rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  color: #fff;
  font-size: 28rpx;
}

.detail-info {
  padding: 30rpx;
}

.info-row {
  display: flex;
  align-items: center;
  margin-bottom: 20rpx;
}

.info-icon {
  font-size: 32rpx;
  margin-right: 16rpx;
}

.info-text {
  font-size: 28rpx;
  color: #333;
}

.detail-action {
  padding: 30rpx;
  border-top: 2rpx solid #f5f5f5;
}

.action-btn {
  width: 100%;
  padding: 24rpx;
  background: #1989fa;
  border-radius: 30rpx;
  text-align: center;
  font-size: 32rpx;
  color: #fff;
  
  &.disabled {
    background: #ccc;
  }
}
</style>