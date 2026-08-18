<template>
  <view class="container">
    <view class="header">
      <text class="header-title">学员管理</text>
    </view>

    <view class="stats-row">
      <view class="stat-card">
        <text class="stat-value">{{ totalStudents }}</text>
        <text class="stat-label">总学员</text>
      </view>
      <view class="stat-card">
        <text class="stat-value">{{ todayBookings }}</text>
        <text class="stat-label">今日预约</text>
      </view>
      <view class="stat-card">
        <text class="stat-value">{{ checkedInCount }}</text>
        <text class="stat-label">已签到</text>
      </view>
    </view>

    <view class="schedule-tabs">
      <scroll-view scroll-x class="tabs-scroll" :show-scrollbar="false">
        <view class="tabs-inner">
          <view
            v-for="schedule in scheduleList"
            :key="schedule.id"
            class="schedule-tab"
            :class="{ active: selectedSchedule === schedule.id }"
            @tap="selectSchedule(schedule.id)"
          >
            <text class="tab-date">{{ formatDate(schedule.start_at) }}</text>
            <text class="tab-time">{{ formatTime(schedule.start_at) }}-{{ formatTime(schedule.end_at) }}</text>
          </view>
        </view>
      </scroll-view>
    </view>

    <scroll-view scroll-y class="student-list" :show-scrollbar="false">
      <view v-if="students.length === 0" class="empty-state">
        <text class="empty-icon">👥</text>
        <text class="empty-text">暂无学员</text>
      </view>

      <view v-for="student in students" :key="student.id" class="student-card">
        <view class="student-avatar">
          <view class="avatar-placeholder">
            <text class="avatar-text">{{ student.nickname?.charAt(0) || '?' }}</text>
          </view>
        </view>

        <view class="student-info">
          <text class="student-name">{{ student.nickname || student.phone }}</text>
          <text class="student-phone">{{ student.phone }}</text>
          <view class="booking-info">
            <text class="booking-time">{{ formatTime(student.booking_time) }}</text>
            <text class="booking-status" :class="getStatusClass(student.booking_status)">
              {{ getStatusText(student.booking_status) }}
            </text>
          </view>
        </view>

        <view class="student-actions">
          <view
            v-if="student.booking_status === 'booked'"
            class="action-btn checkin"
            @tap="handleCheckIn(student.id)"
          >
            <text>签到</text>
          </view>
          <view v-else class="action-btn completed">
            <text>{{ getStatusText(student.booking_status) }}</text>
          </view>
        </view>
      </view>
    </scroll-view>

    <TeacherTabBar currentRoute="/pages/teacher/students/index" />

    <!-- AI 智能助手 -->
    <AiAssistant
      :session-id="'teacher_' + (userId || 'default')"
    />
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { teacherApi, bookingApi } from '@/api'
import { checkLogin } from '@/utils/auth'
import { formatDate, formatTime } from '@/utils/date'
import TeacherTabBar from '@/components/TeacherTabBar.vue'
import AiAssistant from '@/components/AiAssistant.vue'
import { navigateTo } from '@/utils/navigation'

const students = ref<any[]>([])
const scheduleList = ref<any[]>([])
const selectedSchedule = ref<number | null>(null)
const userId = ref('')

// ✅ 页面卸载标记
let isUnmounted = false

const totalStudents = computed(() => students.value.length)
const todayBookings = computed(() => students.value.filter(s => s.booking_status === 'booked').length)
const checkedInCount = computed(() => students.value.filter(s => s.booking_status === 'checked_in').length)

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
    const today = new Date().toISOString().split('T')[0]
    const result = await teacherApi.getSchedules({ start_from: today, start_to: today, status: 1 })
    
    // ✅ 页面已卸载，不再更新数据
    if (isUnmounted) return
    
    scheduleList.value = extractList(result)
    if (scheduleList.value.length > 0) {
      selectedSchedule.value = scheduleList.value[0].id
      loadStudents()
    }
  } catch {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}

const loadStudents = async () => {
  if (!selectedSchedule.value) return
  
  try {
    const result = await bookingApi.list({ schedule_id: selectedSchedule.value })
    
    // ✅ 页面已卸载，不再更新数据
    if (isUnmounted) return
    
    students.value = extractList(result)
  } catch {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}

const selectSchedule = (scheduleId: number) => {
  selectedSchedule.value = scheduleId
  loadStudents()
}

const getStatusClass = (status: string) => {
  switch (status) {
    case 'booked': return 'booked'
    case 'checked_in': return 'checked-in'
    case 'completed': return 'completed'
    default: return 'cancelled'
  }
}

const getStatusText = (status: string) => {
  switch (status) {
    case 'booked': return '已预约'
    case 'checked_in': return '已签到'
    case 'completed': return '已完成'
    case 'cancelled': return '已取消'
    default: return status
  }
}

const handleCheckIn = async (bookingId: number) => {
  uni.showModal({
    title: '确认签到',
    content: '确认该学员已签到？',
    success: async (res) => {
      if (res.confirm) {
        try {
          const result = await bookingApi.checkIn(bookingId)
          if (result.code === 0 || result.code === 200) {
            uni.showToast({ title: '签到成功', icon: 'success' })
            loadStudents()
          } else {
            uni.showToast({ title: result.msg || '签到失败', icon: 'none' })
          }
        } catch {
          uni.showToast({ title: '签到失败', icon: 'none' })
        }
      }
    }
  })
}

const goToCourses = () => {
  navigateTo({ url: '/pages/teacher/courses/index' })
}

const goToSchedule = () => {
  navigateTo({ url: '/pages/teacher/schedule/index' })
}

const goToProfile = () => {
  navigateTo({ url: '/pages/teacher/profile/index' })
}
</script>

<style lang="scss">
/* ✅ 已通过 vite.config.ts 全局注入 scrollbar 样式 */
.container {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 120rpx;
}

.header {
  padding: 60rpx 32rpx 24rpx;
  background: #fff;
}

.header-title {
  font-size: 36rpx;
  font-weight: bold;
}

.stats-row {
  display: flex;
  padding: 24rpx 32rpx;
  background: #fff;
  gap: 16rpx;
  border-top: 1rpx solid #f0f0f0;
}

.stat-card {
  flex: 1;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 16rpx;
  padding: 24rpx;
  text-align: center;
}

.stat-value {
  font-size: 40rpx;
  font-weight: bold;
  color: #fff;
  display: block;
  margin-bottom: 8rpx;
}

.stat-label {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.8);
}

.schedule-tabs {
  background: #fff;
  border-top: 1rpx solid #f0f0f0;
}

.tabs-scroll {
  white-space: nowrap;
  padding: 20rpx 0;
}

.tabs-inner {
  display: inline-flex;
  padding: 0 32rpx;
  gap: 16rpx;
}

.schedule-tab {
  flex-shrink: 0;
  padding: 16rpx 24rpx;
  background: #f5f5f5;
  border-radius: 12rpx;
  text-align: center;

  &.active {
    background: #667eea;

    .tab-date, .tab-time {
      color: #fff;
    }
  }
}

.tab-date {
  font-size: 24rpx;
  color: #666;
  display: block;
  margin-bottom: 4rpx;
}

.tab-time {
  font-size: 22rpx;
  color: #999;
}

.student-list {
  height: calc(100vh - 400rpx);
  padding: 24rpx 32rpx;
  padding-bottom: 180rpx;     // ✅ 底部舒适间距，与 TabBar 保持距离
  box-sizing: border-box;
  overflow-y: auto;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 120rpx 0;
}

.empty-icon {
  font-size: 120rpx;
  margin-bottom: 32rpx;
}

.empty-text {
  font-size: 28rpx;
  color: #999;
}

.student-card {
  display: flex;
  align-items: center;
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 20rpx;
}

.student-avatar {
  width: 88rpx;
  height: 88rpx;
  border-radius: 50%;
  overflow: hidden;
  margin-right: 20rpx;
}

.avatar-placeholder {
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-text {
  font-size: 36rpx;
  color: #fff;
  font-weight: bold;
}

.student-info {
  flex: 1;
}

.student-name {
  font-size: 30rpx;
  font-weight: bold;
  display: block;
  margin-bottom: 8rpx;
}

.student-phone {
  font-size: 24rpx;
  color: #999;
  display: block;
  margin-bottom: 8rpx;
}

.booking-info {
  display: flex;
  align-items: center;
}

.booking-time {
  font-size: 24rpx;
  color: #667eea;
  margin-right: 16rpx;
}

.booking-status {
  font-size: 22rpx;
  padding: 4rpx 12rpx;
  border-radius: 20rpx;

  &.booked {
    background: #fff7e6;
    color: #fa8c16;
  }

  &.checked-in {
    background: #e6f7ff;
    color: #1890ff;
  }

  &.completed {
    background: #f6ffed;
    color: #52c41a;
  }

  &.cancelled {
    background: #fff2f0;
    color: #ff4d4f;
  }
}

.student-actions {
  margin-left: 20rpx;
}

.action-btn {
  padding: 16rpx 32rpx;
  border-radius: 40rpx;
  font-size: 26rpx;

  &.checkin {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: #fff;
  }

  &.completed {
    background: #f5f5f5;
    color: #999;
  }
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
</style>