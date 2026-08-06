<template>
  <view class="page">
    <view class="tabs">
      <view 
        class="tab-item" 
        :class="{ active: activeTab === 'all' }"
        @click="setTab('all')"
      >
        全部
      </view>
      <view 
        class="tab-item" 
        :class="{ active: activeTab === 'pending' }"
        @click="setTab('pending')"
      >
        待上课
      </view>
      <view 
        class="tab-item" 
        :class="{ active: activeTab === 'completed' }"
        @click="setTab('completed')"
      >
        已完成
      </view>
    </view>

    <view class="booking-list">
      <view 
        class="booking-card" 
        v-for="booking in filteredBookings" 
        :key="booking.id"
      >
        <view class="booking-header">
          <view class="booking-status" :class="getStatusClass(booking.status)">
            <text>{{ getStatusText(booking.status) }}</text>
          </view>
          <text class="booking-date">{{ formatDate(booking.schedule?.start_at) }}</text>
        </view>
        
        <view class="booking-body">
          <view class="booking-course">
            <text class="course-name">{{ booking.schedule?.course_name }}</text>
            <view class="course-meta">
              <text class="teacher-name">👨‍🏫 {{ booking.schedule?.teacher_name }}</text>
              <text class="classroom-name">🏠 {{ booking.schedule?.classroom_name }}</text>
            </view>
          </view>
          
          <view class="booking-time">
            <text class="time-range">{{ formatTime(booking.schedule?.start_at) }} - {{ formatTime(booking.schedule?.end_at) }}</text>
            <text class="duration">{{ booking.schedule?.course?.duration_minutes }}分钟</text>
          </view>
        </view>

        <view class="booking-footer">
          <view class="price-info">
            <text class="price-label">课程费用</text>
            <text class="price-value">¥{{ booking.schedule?.course?.price }}</text>
          </view>
          <view class="action-area">
            <view 
              class="cancel-btn" 
              v-if="canCancel(booking)"
              @click="handleCancel(booking.id)"
            >
              <text>取消预约</text>
            </view>
            <view 
              class="checkin-btn" 
              v-else-if="booking.status === 1"
            >
              <text>已预约</text>
            </view>
          </view>
        </view>
      </view>
    </view>

    <view class="empty-state" v-if="filteredBookings.length === 0">
      <text class="empty-icon">📋</text>
      <text class="empty-text">暂无预约记录</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { bookingApi } from '@/api'

const activeTab = ref('all')
const bookings = ref<any[]>([])

onMounted(() => {
  loadBookings()
})

async function loadBookings() {
  try {
    const res = await bookingApi.list({ page_size: 50 })
    bookings.value = res.data.items || []
  } catch (e) {
    console.error('加载预约失败', e)
  }
}

const filteredBookings = computed(() => {
  if (activeTab.value === 'all') return bookings.value
  if (activeTab.value === 'pending') {
    return bookings.value.filter(b => b.status === 1 || b.status === 3)
  }
  if (activeTab.value === 'completed') {
    return bookings.value.filter(b => b.status === 4)
  }
  return bookings.value
})

function setTab(tab: string) {
  activeTab.value = tab
}

function getStatusClass(status: number) {
  switch (status) {
    case 1: return 'status-pending'
    case 2: return 'status-cancelled'
    case 3: return 'status-checked-in'
    case 4: return 'status-completed'
    default: return 'status-pending'
  }
}

function getStatusText(status: number) {
  switch (status) {
    case 1: return '待上课'
    case 2: return '已取消'
    case 3: return '已签到'
    case 4: return '已完成'
    default: return '未知'
  }
}

function formatDate(dateStr: string) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`
}

function formatTime(dateStr: string) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
}

function canCancel(booking: any) {
  if (booking.status !== 1) return false
  const startAt = new Date(booking.schedule?.start_at)
  const now = new Date()
  const diffHours = (startAt.getTime() - now.getTime()) / (1000 * 60 * 60)
  return diffHours > 1.5
}

async function handleCancel(bookingId: number) {
  uni.showModal({
    title: '提示',
    content: '确定要取消预约吗？',
    success: async (res) => {
      if (res.confirm) {
        try {
          await bookingApi.cancel(bookingId)
          uni.showToast({ title: '取消成功', icon: 'success' })
          loadBookings()
        } catch (e: any) {
          uni.showToast({ title: e?.response?.data?.msg || '取消失败', icon: 'none' })
        }
      }
    }
  })
}
</script>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 120rpx;
}

.tabs {
  display: flex;
  background: #fff;
  padding: 20rpx 30rpx;
  gap: 20rpx;
}

.tab-item {
  flex: 1;
  text-align: center;
  padding: 20rpx;
  font-size: 28rpx;
  color: #666;
  border-radius: 30rpx;
  background: #f5f5f5;
  
  &.active {
    background: #1989fa;
    color: #fff;
  }
}

.booking-list {
  padding: 20rpx 30rpx;
}

.booking-card {
  background: #fff;
  border-radius: 20rpx;
  padding: 24rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.06);
}

.booking-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}

.booking-status {
  padding: 8rpx 20rpx;
  border-radius: 20rpx;
  font-size: 24rpx;
}

.status-pending {
  background: #fff3e0;
  color: #ff9800;
}

.status-cancelled {
  background: #f5f5f5;
  color: #999;
}

.status-checked-in {
  background: #e8f5e9;
  color: #4caf50;
}

.status-completed {
  background: #e3f2fd;
  color: #1989fa;
}

.booking-date {
  font-size: 26rpx;
  color: #999;
}

.booking-body {
  display: flex;
  justify-content: space-between;
  padding: 20rpx 0;
  border-top: 2rpx solid #f5f5f5;
  border-bottom: 2rpx solid #f5f5f5;
}

.booking-course {
  flex: 1;
}

.course-name {
  font-size: 32rpx;
  font-weight: bold;
  color: #333;
  display: block;
}

.course-meta {
  display: flex;
  gap: 20rpx;
  margin-top: 12rpx;
}

.teacher-name,
.classroom-name {
  font-size: 24rpx;
  color: #999;
}

.booking-time {
  text-align: right;
}

.time-range {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
  display: block;
}

.duration {
  font-size: 24rpx;
  color: #999;
  margin-top: 8rpx;
  display: block;
}

.booking-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 20rpx;
}

.price-info {
  display: flex;
  flex-direction: column;
}

.price-label {
  font-size: 22rpx;
  color: #999;
}

.price-value {
  font-size: 32rpx;
  font-weight: bold;
  color: #ff6b6b;
}

.action-area {
  flex-shrink: 0;
}

.cancel-btn {
  padding: 16rpx 32rpx;
  background: #fff3e0;
  border-radius: 30rpx;
  font-size: 26rpx;
  color: #ff9800;
}

.checkin-btn {
  padding: 16rpx 32rpx;
  background: #f5f5f5;
  border-radius: 30rpx;
  font-size: 26rpx;
  color: #999;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 150rpx 0;
}

.empty-icon {
  font-size: 100rpx;
  margin-bottom: 30rpx;
}

.empty-text {
  font-size: 30rpx;
  color: #999;
}
</style>