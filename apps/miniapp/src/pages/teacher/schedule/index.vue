<template>
  <view class="container">
    <view class="header">
      <text class="header-title">排期管理</text>
      <button class="add-btn" @tap="goToCreate">
        <text class="add-icon">+</text>
        <text>添加排期</text>
      </button>
    </view>

    <view class="date-selector">
      <view class="date-btn" @tap="prevWeek">
        <text>←</text>
      </view>
      <text class="date-range">{{ dateRangeText }}</text>
      <view class="date-btn" @tap="nextWeek">
        <text>→</text>
      </view>
    </view>

    <view class="week-header">
      <view v-for="day in weekDays" :key="day.date" class="day-item">
        <text class="day-name">{{ day.name }}</text>
        <text class="day-date" :class="{ today: day.isToday }">{{ day.day }}</text>
      </view>
    </view>

    <scroll-view scroll-y class="schedule-scroll" :show-scrollbar="false">
      <view class="time-slot-list">
        <view v-for="slot in timeSlots" :key="slot.time" class="time-slot">
          <view class="time-label">
            <text>{{ slot.time }}</text>
          </view>
          <view class="schedule-grid">
            <view
              v-for="day in weekDays"
              :key="day.date"
              class="grid-cell"
            >
              <view
                v-for="schedule in getSchedulesForCell(day.date, slot.time)"
                :key="schedule.id"
                class="schedule-block"
                :class="{ cancelled: schedule.status === 0 }"
                @tap="showScheduleDetail(schedule)"
              >
                <text class="schedule-course">{{ schedule.course_name }}</text>
                <text class="schedule-count">{{ schedule.booked_count }}/{{ schedule.capacity }}</text>
              </view>
            </view>
          </view>
        </view>
      </view>
    </scroll-view>

    <TeacherTabBar currentRoute="/pages/teacher/schedule/index" />

    <!-- AI 智能助手 -->
    <AiAssistant
      :session-id="'teacher_' + (userId || 'default')"
    />

    <view v-if="showDetail" class="modal-overlay" @tap="closeDetail">
      <view class="detail-modal" @tap.stop>
        <view class="modal-header">
          <text class="modal-title">排期详情</text>
          <view class="close-btn" @tap="closeDetail">
            <text>✕</text>
          </view>
        </view>
        <view v-if="selectedSchedule" class="modal-body">
          <view class="detail-info">
            <text class="info-label">课程名称</text>
            <text class="info-value">{{ selectedSchedule.course_name }}</text>
          </view>
          <view class="detail-info">
            <text class="info-label">上课时间</text>
            <text class="info-value">{{ formatDateTime(selectedSchedule.start_at) }}</text>
          </view>
          <view class="detail-info">
            <text class="info-label">教室</text>
            <text class="info-value">{{ selectedSchedule.classroom_name || '未安排' }}</text>
          </view>
          <view class="detail-info">
            <text class="info-label">预约人数</text>
            <text class="info-value">{{ selectedSchedule.booked_count }}/{{ selectedSchedule.capacity }}</text>
          </view>
          <view class="detail-info">
            <text class="info-label">状态</text>
            <text class="info-value" :class="selectedSchedule.status === 1 ? 'active' : 'cancelled'">
              {{ selectedSchedule.status === 1 ? '正常' : '已取消' }}
            </text>
          </view>
        </view>
        <view class="modal-footer">
          <button class="modal-btn cancel" @tap="cancelSchedule">取消排期</button>
          <button class="modal-btn edit" @tap="editSchedule">编辑排期</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { teacherApi, scheduleApi } from '@/api'
import { checkLogin } from '@/utils/auth'
import { formatDateTime } from '@/utils/date'
import TeacherTabBar from '@/components/TeacherTabBar.vue'
import AiAssistant from '@/components/AiAssistant.vue'
import { navigateTo } from '@/utils/navigation'

const currentWeekStart = ref('')
const userId = ref('')
const schedules = ref<any[]>([])
const showDetail = ref(false)
const selectedSchedule = ref<any>(null)

// ✅ 页面卸载标记
let isUnmounted = false

const timeSlots = [
  { time: '08:00' }, { time: '09:00' }, { time: '10:00' }, { time: '11:00' },
  { time: '12:00' }, { time: '13:00' }, { time: '14:00' }, { time: '15:00' },
  { time: '16:00' }, { time: '17:00' }, { time: '18:00' }, { time: '19:00' },
  { time: '20:00' }, { time: '21:00' }
]

const weekDays = computed(() => {
  const days = []
  const dayNames = ['日', '一', '二', '三', '四', '五', '六']
  const today = new Date()
  const startDate = currentWeekStart.value ? new Date(currentWeekStart.value) : getWeekStart(today)
  
  for (let i = 0; i < 7; i++) {
    const date = new Date(startDate)
    date.setDate(startDate.getDate() + i)
    days.push({
      date: date.toISOString().split('T')[0],
      name: dayNames[date.getDay()],
      day: date.getDate(),
      isToday: date.toISOString().split('T')[0] === today.toISOString().split('T')[0]
    })
  }
  return days
})

const dateRangeText = computed(() => {
  if (weekDays.value.length >= 2) {
    return `${weekDays.value[0].date} ~ ${weekDays.value[6].date}`
  }
  return ''
})

function getWeekStart(date: Date): Date {
  const d = new Date(date)
  const day = d.getDay()
  const diff = d.getDate() - day + (day === 0 ? -6 : 1)
  return new Date(d.setDate(diff))
}

onMounted(() => {
  if (!checkLogin('teacher')) return

  const userInfo = uni.getStorageSync('user_info')
  if (userInfo) {
    try {
      const parsed = JSON.parse(userInfo)
      userId.value = parsed.id || ''
    } catch {}
  }

  loadSchedules()
})

onUnmounted(() => {
  isUnmounted = true
})

const loadSchedules = async () => {
  try {
    const result = await teacherApi.getSchedules({
      start_from: weekDays.value[0]?.date,
      start_to: weekDays.value[6]?.date
    })
    
    // ✅ 页面已卸载，不再更新数据
    if (isUnmounted) return
    
    schedules.value = extractList(result)
  } catch {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}

const prevWeek = () => {
  const start = new Date(currentWeekStart.value || new Date())
  start.setDate(start.getDate() - 7)
  currentWeekStart.value = start.toISOString().split('T')[0]
  loadSchedules()
}

const nextWeek = () => {
  const start = new Date(currentWeekStart.value || new Date())
  start.setDate(start.getDate() + 7)
  currentWeekStart.value = start.toISOString().split('T')[0]
  loadSchedules()
}

const getSchedulesForCell = (date: string, time: string) => {
  return schedules.value.filter(schedule => {
    const scheduleDate = schedule.start_at.split('T')[0]
    const scheduleTime = schedule.start_at.split('T')[1]?.substring(0, 5)
    return scheduleDate === date && scheduleTime === time
  })
}

const showScheduleDetail = (schedule: any) => {
  selectedSchedule.value = schedule
  showDetail.value = true
}

const closeDetail = () => {
  showDetail.value = false
  selectedSchedule.value = null
}

const cancelSchedule = async () => {
  if (!selectedSchedule.value) return
  
  uni.showModal({
    title: '确认取消',
    content: '取消后将通知已预约学员，确定要取消吗？',
    success: async (res) => {
      if (res.confirm) {
        try {
          const result = await scheduleApi.cancel(selectedSchedule.value.id)
          if (result.code === 0 || result.code === 200) {
            uni.showToast({ title: '已取消', icon: 'success' })
            closeDetail()
            loadSchedules()
          } else {
            uni.showToast({ title: result.msg || '取消失败', icon: 'none' })
          }
        } catch {
          uni.showToast({ title: '取消失败', icon: 'none' })
        }
      }
    }
  })
}

const editSchedule = () => {
  closeDetail()
  if (selectedSchedule.value) {
    navigateTo({ url: `/pages/teacher/schedule/form?id=${selectedSchedule.value.id}` })
  }
}

const goToCreate = () => {
  navigateTo({ url: '/pages/teacher/schedule/form' })
}

const goToCourses = () => {
  navigateTo({ url: '/pages/teacher/courses/index' })
}

const goToStudents = () => {
  navigateTo({ url: '/pages/teacher/students/index' })
}

const goToProfile = () => {
  navigateTo({ url: '/pages/teacher/profile/index' })
}
</script>

<style lang="scss">
/* ✅ 已通过 vite.config.ts 全局注入 scrollbar 样式 */

// ✨ 教师排期页面 - 高级轻奢风格升级

.container {
  min-height: 100vh;
  background: $bg-primary;                 // ✅ 米白背景（替代#f5f5f5）
  padding-bottom: 120rpx;
}

// 🎯 头部区域 - 玻璃态设计
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 60rpx $space-lg $space-lg;      // ✅ 统一间距
  background: rgba(255, 255, 255, 0.9);   // ✅ 半透明白色（替代纯白）
  backdrop-filter: blur(10rpx);
  position: relative;

  &::after {                              // 底部装饰线
    content: '';
    position: absolute;
    bottom: 0;
    left: $space-lg;
    right: $space-lg;
    height: 1rpx;
    background: linear-gradient(
      90deg,
      transparent,
      $border-light 50%,
      transparent
    );
  }
}

.header-title {
  @include text-h1; // ✅ 使用Design System字体
  color: $text-primary;
}

// ➕ 添加按钮 - 品牌渐变
.add-btn {
  display: flex;
  align-items: center;
  background: $primary-gradient;           // ✅ 香槟金渐变（替代蓝紫渐变）
  border: none;
  border-radius: $radius-full;            // ✅ 统一圆角
  padding: $space-sm $space-md;
  color: #fff;
  @include text-body;
  box-shadow: $shadow-sm;
  transition: transform $duration-fast $ease-standard,
              box-shadow $duration-fast $ease-standard,
              background $duration-fast $ease-standard;

  &:active {
    transform: scale(0.97);
    box-shadow: $shadow-card;
  }
}

.add-icon {
  font-size: 32rpx;
  margin-right: $space-xs;
}

// 📅 日期选择器 - 玻璃态设计
.date-selector {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: $space-md $space-lg;           // ✅ 统一间距
  background: rgba(255, 255, 255, 0.85);   // ✅ 半透明
  backdrop-filter: blur(10rpx);
}

.date-btn {
  width: 64rpx;
  height: 64rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(201, 166, 107, 0.08); // ✅ 品牌色浅背景
  border-radius: 50%;
  @include text-body;
  color: $text-primary;
  transition: background $duration-fast $ease-standard,
              transform $duration-fast $ease-standard,
              color $duration-fast $ease-standard;

  &:active {
    background: rgba(201, 166, 107, 0.15);
    transform: scale(0.95);
  }
}

.date-range {
  @include text-body;
  color: $text-primary;
}

// 📆 星期标题行
.week-header {
  display: flex;
  background: rgba(255, 255, 255, 0.9);   // ✅ 半透明
  backdrop-filter: blur(8rpx);
  padding: $space-sm 0;
  border-bottom: 1rpx solid $border-light; // ✅ 替代#f0f0f0
}

.day-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.day-name {
  @include text-caption;
  color: $text-tertiary;                  // ✅ 替代#999
  margin-bottom: $space-xs;
}

.day-date {
  width: 56rpx;
  height: 56rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  @include text-body;
  transition: background $duration-fast $ease-standard,
              color $duration-fast $ease-standard,
              box-shadow $duration-fast $ease-standard,
              font-weight $duration-fast $ease-standard;

  &.today {
    background: $primary-gradient;         // ✅ 品牌渐变（替代#667eea）
    color: #fff;
    box-shadow: $shadow-sm;
  }
}

// 📜 排期滚动区域
.schedule-scroll {
  height: calc(100vh - 380rpx);
  padding: $space-md $space-lg;
  padding-bottom: 180rpx;     // ✅ 底部舒适间距，与 TabBar 保持距离
  box-sizing: border-box;
  overflow-y: auto;
}

// ⏰ 时间段列表 - 高级卡片设计
.time-slot-list {
  background: $card-background;            // ✅ 卡片背景（替代#fff）
  border-radius: $radius-lg;              // ✅ 统一圆角（替代16rpx）
  overflow: hidden;
  box-shadow: $shadow-card;               // ✅ 添加阴影
}

.time-slot {
  display: flex;
  border-bottom: 1rpx solid $border-light; // ✅ 替代#f0f0f0

  &:last-child {
    border-bottom: none;
  }

  &:hover {                               // 悬停效果（如果支持）
    background: rgba(245, 237, 228, 0.3);
  }
}

// 🕐 时间标签
.time-label {
  width: 100rpx;
  padding: $space-sm $space-xs;
  text-align: center;
  background: $bg-tertiary;               // ✅ 三级背景（替代#fafafa）
  border-right: 1rpx solid $border-light;  // ✅ 替代#f0f0f0

  text {
    @include text-caption;
    color: $text-secondary;                // ✅ 替代#999
  }
}

// 📊 课程网格
.schedule-grid {
  flex: 1;
  display: flex;
}

.grid-cell {
  flex: 1;
  min-height: 80rpx;
  padding: $space-xs;
  border-right: 1rpx solid $border-light;  // ✅ 替代#f0f0f0

  &:last-child {
    border-right: none;
  }
}

// 📚 课程块 - 品牌渐变
.schedule-block {
  background: $primary-gradient;           // ✅ 香槟金渐变（替代蓝紫渐变）
  border-radius: $radius-sm;              // ✅ 统一圆角（替代8rpx）
  padding: $space-xs;
  margin-bottom: $space-xs;
  min-height: 60rpx;
  transition: transform $duration-fast $ease-standard,
              box-shadow $duration-fast $ease-standard,
              opacity $duration-fast $ease-standard;

  &:active {
    transform: scale(0.98);
    box-shadow: $shadow-sm;
  }

  &.cancelled {
    background: $bg-tertiary;             // ✅ 灰色背景（替代#e0e0e0）

    .schedule-course,
    .schedule-count {
      color: $text-tertiary;              // ✅ 取消状态使用浅色文字
    }
  }
}

.schedule-course {
  @include text-caption;
  color: #fff;
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.schedule-count {
  @include text-caption;
  color: rgba(255, 255, 255, 0.85);       // ✅ 提高不透明度
}

.tab-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  background: #fff;
  padding: 16rpx 0 32rpx;
  border-top: 1rpx solid #f0f0f0;
}

.tab-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;

  &.active {
    .tab-icon, .tab-text {
      color: #667eea;
    }
  }
}

.tab-icon {
  font-size: 40rpx;
  margin-bottom: 8rpx;
  color: #999;
}

.tab-text {
  font-size: 22rpx;
  color: #999;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.detail-modal {
  width: 90%;
  max-width: 640rpx;
  background: #fff;
  border-radius: 20rpx;
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 32rpx;
  border-bottom: 1rpx solid #f0f0f0;
}

.modal-title {
  font-size: 32rpx;
  font-weight: bold;
}

.close-btn {
  width: 48rpx;
  height: 48rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32rpx;
  color: #999;
}

.modal-body {
  padding: 32rpx;
}

.detail-info {
  margin-bottom: 24rpx;
}

.info-label {
  font-size: 26rpx;
  color: #999;
  margin-bottom: 8rpx;
  display: block;
}

.info-value {
  font-size: 28rpx;

  &.active {
    color: #52c41a;
  }

  &.cancelled {
    color: #ff4d4f;
  }
}

.modal-footer {
  display: flex;
  padding: 24rpx 32rpx;
  border-top: 1rpx solid #f0f0f0;
}

.modal-btn {
  flex: 1;
  height: 80rpx;
  border-radius: 12rpx;
  font-size: 28rpx;
  margin-right: 16rpx;

  &:last-child {
    margin-right: 0;
  }

  &.cancel {
    background: #f5f5f5;
    color: #ff4d4f;
    border: none;
  }

  &.edit {
    background: #667eea;
    color: #fff;
    border: none;
  }
}
</style>