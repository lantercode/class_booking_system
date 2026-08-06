<template>
  <view class="page">
    <scroll-view scroll-y class="scroll-view">
      <view class="cover-area">
        <image class="cover-image" :src="course.cover_url || '/static/default-course.png'" mode="aspectFill" />
        <view class="cover-overlay">
          <text class="course-name">{{ course.name }}</text>
        </view>
      </view>

      <view class="info-card">
        <view class="info-row">
          <view class="info-item">
            <text class="info-icon">💰</text>
            <text class="info-value">¥{{ course.price }}</text>
            <text class="info-label">单价</text>
          </view>
          <view class="info-item">
            <text class="info-icon">⏱️</text>
            <text class="info-value">{{ course.duration_minutes }}</text>
            <text class="info-label">分钟</text>
          </view>
          <view class="info-item">
            <text class="info-icon">👥</text>
            <text class="info-value">{{ course.max_capacity }}</text>
            <text class="info-label">人数上限</text>
          </view>
        </view>
      </view>

      <view class="section">
        <view class="section-header">
          <text class="section-title">课程介绍</text>
        </view>
        <view class="section-content">
          <text class="description">{{ course.description }}</text>
        </view>
      </view>

      <view class="section">
        <view class="section-header">
          <text class="section-title">近期排期</text>
        </view>
        <view class="schedule-list">
          <view 
            class="schedule-item" 
            v-for="schedule in schedules" 
            :key="schedule.id"
            @click="handleBooking(schedule)"
          >
            <view class="schedule-left">
              <text class="schedule-date">{{ formatDate(schedule.start_at) }}</text>
              <text class="schedule-time">{{ formatTime(schedule.start_at) }} - {{ formatTime(schedule.end_at) }}</text>
            </view>
            <view class="schedule-right">
              <text class="schedule-teacher">{{ schedule.teacher_name }}</text>
              <text class="schedule-classroom">{{ schedule.classroom_name }}</text>
            </view>
            <view class="schedule-action">
              <view 
                class="action-btn" 
                :class="{ disabled: schedule.booked_count >= schedule.capacity }"
              >
                <text>{{ schedule.booked_count >= schedule.capacity ? '已满' : '预约' }}</text>
              </view>
            </view>
          </view>
        </view>
      </view>

      <view class="section">
        <view class="section-header">
          <text class="section-title">课程标签</text>
        </view>
        <view class="tag-list">
          <text class="tag">{{ course.category }}</text>
          <text class="tag">{{ course.level }}</text>
        </view>
      </view>
    </scroll-view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { courseApi, scheduleApi, bookingApi } from '@/api'

const course = ref<any>({
  name: '',
  description: '',
  price: 0,
  duration_minutes: 0,
  max_capacity: 0,
  category: '',
  level: '',
  cover_url: ''
})

const schedules = ref<any[]>([])

onLoad((options: any) => {
  const courseId = options?.id
  if (courseId) {
    loadCourse(courseId)
    loadSchedules(courseId)
  }
})

async function loadCourse(id: number) {
  try {
    const res = await courseApi.get(id)
    course.value = res.data
  } catch (e) {
    console.error('加载课程详情失败', e)
  }
}

async function loadSchedules(courseId: number) {
  try {
    const res = await scheduleApi.list({ course_id: courseId, page_size: 20 })
    schedules.value = res.data.items || []
  } catch (e) {
    console.error('加载排期失败', e)
  }
}

function formatDate(dateStr: string) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return `${date.getMonth() + 1}月${date.getDate()}日`
}

function formatTime(dateStr: string) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
}

async function handleBooking(schedule: any) {
  if (schedule.booked_count >= schedule.capacity) {
    uni.showToast({ title: '该排期已满', icon: 'none' })
    return
  }

  try {
    const res = await bookingApi.create({ schedule_id: schedule.id })
    uni.showToast({ title: '预约成功', icon: 'success' })
    schedule.booked_count++
  } catch (e: any) {
    uni.showToast({ title: e?.response?.data?.msg || '预约失败', icon: 'none' })
  }
}
</script>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
}

.scroll-view {
  height: 100vh;
  padding-bottom: 40rpx;
}

.cover-area {
  position: relative;
  height: 400rpx;
}

.cover-image {
  width: 100%;
  height: 100%;
}

.cover-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.6));
  padding: 60rpx 30rpx 30rpx;
}

.course-name {
  font-size: 40rpx;
  font-weight: bold;
  color: #fff;
}

.info-card {
  margin: -30rpx 30rpx 20rpx;
  background: #fff;
  border-radius: 20rpx;
  padding: 30rpx;
  box-shadow: 0 8rpx 32rpx rgba(0, 0, 0, 0.1);
}

.info-row {
  display: flex;
  justify-content: space-around;
}

.info-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.info-icon {
  font-size: 40rpx;
  margin-bottom: 12rpx;
}

.info-value {
  font-size: 36rpx;
  font-weight: bold;
  color: #333;
}

.info-label {
  font-size: 24rpx;
  color: #999;
  margin-top: 8rpx;
}

.section {
  background: #fff;
  margin: 20rpx 30rpx;
  border-radius: 20rpx;
  padding: 30rpx;
}

.section-header {
  margin-bottom: 20rpx;
}

.section-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #333;
}

.section-content {
  font-size: 28rpx;
  line-height: 1.8;
  color: #666;
}

.description {
  font-size: 28rpx;
  line-height: 1.8;
  color: #666;
}

.schedule-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.schedule-item {
  display: flex;
  align-items: center;
  padding: 24rpx;
  background: #f9f9f9;
  border-radius: 16rpx;
}

.schedule-left {
  flex: 1;
}

.schedule-date {
  font-size: 26rpx;
  color: #999;
  display: block;
}

.schedule-time {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
  margin-top: 8rpx;
  display: block;
}

.schedule-right {
  flex: 1;
  padding: 0 20rpx;
}

.schedule-teacher {
  font-size: 26rpx;
  color: #333;
  display: block;
}

.schedule-classroom {
  font-size: 24rpx;
  color: #999;
  margin-top: 8rpx;
  display: block;
}

.schedule-action {
  flex-shrink: 0;
}

.action-btn {
  padding: 16rpx 32rpx;
  background: #1989fa;
  border-radius: 30rpx;
  font-size: 26rpx;
  color: #fff;
  
  &.disabled {
    background: #ccc;
  }
}

.tag-list {
  display: flex;
  gap: 16rpx;
}

.tag {
  padding: 12rpx 24rpx;
  background: #f0f5ff;
  color: #1989fa;
  font-size: 24rpx;
  border-radius: 20rpx;
}
</style>