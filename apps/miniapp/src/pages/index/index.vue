<template>
  <view class="page">
    <view class="header">
      <view class="logo-area">
        <view class="logo">
          <text class="logo-text">💃</text>
        </view>
        <view class="title-area">
          <text class="title">舞蹈约课</text>
          <text class="subtitle">发现精彩课程</text>
        </view>
      </view>
    </view>

    <view class="search-bar">
      <view class="search-input-wrap">
        <text class="search-icon">🔍</text>
        <input 
          class="search-input" 
          placeholder="搜索课程" 
          @confirm="handleSearch"
        />
      </view>
    </view>

    <view class="section">
      <view class="section-header">
        <text class="section-title">热门课程</text>
        <text class="section-more" @click="goToCourseList">查看全部 →</text>
      </view>
      <view class="course-list">
        <view 
          class="course-card" 
          v-for="course in courses" 
          :key="course.id"
          @click="goToCourseDetail(course.id)"
        >
          <image class="course-cover" :src="course.cover_url || '/static/default-course.png'" mode="aspectFill" />
          <view class="course-info">
            <text class="course-name">{{ course.name }}</text>
            <view class="course-meta">
              <text class="course-category">{{ course.category }}</text>
              <text class="course-level">{{ course.level }}</text>
            </view>
            <view class="course-footer">
              <text class="course-price">¥{{ course.price }}</text>
              <text class="course-duration">{{ course.duration_minutes }}分钟</text>
            </view>
          </view>
        </view>
      </view>
    </view>

    <view class="section">
      <view class="section-header">
        <text class="section-title">今日排期</text>
      </view>
      <view class="schedule-list">
        <view 
          class="schedule-item" 
          v-for="schedule in todaySchedules" 
          :key="schedule.id"
          @click="goToBooking(schedule.id)"
        >
          <view class="schedule-time">
            <text class="time-start">{{ formatTime(schedule.start_at) }}</text>
            <text class="time-divider">-</text>
            <text class="time-end">{{ formatTime(schedule.end_at) }}</text>
          </view>
          <view class="schedule-info">
            <text class="schedule-course">{{ schedule.course_name }}</text>
            <text class="schedule-teacher">{{ schedule.teacher_name }}</text>
          </view>
          <view class="schedule-status" :class="getBookingStatus(schedule.booked_count, schedule.capacity)">
            <text>{{ getBookingText(schedule.booked_count, schedule.capacity) }}</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { courseApi, scheduleApi } from '@/api'

const courses = ref<any[]>([])
const todaySchedules = ref<any[]>([])

onMounted(() => {
  loadCourses()
  loadTodaySchedules()
})

async function loadCourses() {
  try {
    const res = await courseApi.list({ page_size: 6 })
    courses.value = res.data.items || []
  } catch (e) {
    console.error('加载课程失败', e)
  }
}

async function loadTodaySchedules() {
  try {
    const res = await scheduleApi.list({ page_size: 10 })
    todaySchedules.value = res.data.items || []
  } catch (e) {
    console.error('加载排期失败', e)
  }
}

function formatTime(dateStr: string) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
}

function getBookingStatus(booked: number, capacity: number) {
  const ratio = booked / capacity
  if (ratio >= 1) return 'status-full'
  if (ratio >= 0.8) return 'status-almost-full'
  return 'status-available'
}

function getBookingText(booked: number, capacity: number) {
  if (booked >= capacity) return '已满'
  return `${booked}/${capacity}`
}

function handleSearch(e: any) {
  const keyword = e.detail.value
  uni.navigateTo({ url: `/pages/course/list?keyword=${keyword}` })
}

function goToCourseList() {
  uni.switchTab({ url: '/pages/course/list' })
}

function goToCourseDetail(id: number) {
  uni.navigateTo({ url: `/pages/course/detail?id=${id}` })
}

function goToBooking(id: number) {
  uni.navigateTo({ url: `/pages/course/detail?schedule_id=${id}` })
}
</script>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 120rpx;
}

.header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 60rpx 30rpx 40rpx;
  border-radius: 0 0 40rpx 40rpx;
}

.logo-area {
  display: flex;
  align-items: center;
  gap: 20rpx;
}

.logo {
  width: 80rpx;
  height: 80rpx;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-text {
  font-size: 40rpx;
}

.title-area {
  display: flex;
  flex-direction: column;
}

.title {
  font-size: 40rpx;
  font-weight: bold;
  color: #fff;
}

.subtitle {
  font-size: 26rpx;
  color: rgba(255, 255, 255, 0.8);
  margin-top: 4rpx;
}

.search-bar {
  padding: 20rpx 30rpx;
  margin-top: -20rpx;
}

.search-input-wrap {
  display: flex;
  align-items: center;
  background: #fff;
  border-radius: 40rpx;
  padding: 20rpx 30rpx;
  box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.1);
}

.search-icon {
  font-size: 32rpx;
  margin-right: 16rpx;
}

.search-input {
  flex: 1;
  font-size: 28rpx;
}

.section {
  padding: 20rpx 30rpx;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}

.section-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #333;
}

.section-more {
  font-size: 26rpx;
  color: #1989fa;
}

.course-list {
  display: flex;
  flex-wrap: wrap;
  gap: 20rpx;
}

.course-card {
  width: calc(50% - 10rpx);
  background: #fff;
  border-radius: 20rpx;
  overflow: hidden;
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.06);
}

.course-cover {
  width: 100%;
  height: 200rpx;
}

.course-info {
  padding: 20rpx;
}

.course-name {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
  display: block;
}

.course-meta {
  display: flex;
  gap: 16rpx;
  margin-top: 12rpx;
}

.course-category,
.course-level {
  font-size: 22rpx;
  color: #999;
  background: #f5f5f5;
  padding: 6rpx 16rpx;
  border-radius: 20rpx;
}

.course-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16rpx;
}

.course-price {
  font-size: 32rpx;
  font-weight: bold;
  color: #ff6b6b;
}

.course-duration {
  font-size: 22rpx;
  color: #999;
}

.schedule-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.schedule-item {
  display: flex;
  align-items: center;
  background: #fff;
  padding: 24rpx;
  border-radius: 16rpx;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.04);
}

.schedule-time {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-right: 24rpx;
  border-right: 2rpx solid #f0f0f0;
}

.time-start,
.time-end {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
}

.time-divider {
  font-size: 20rpx;
  color: #ddd;
  margin: 4rpx 0;
}

.schedule-info {
  flex: 1;
  padding: 0 24rpx;
}

.schedule-course {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
  display: block;
}

.schedule-teacher {
  font-size: 24rpx;
  color: #999;
  margin-top: 8rpx;
  display: block;
}

.schedule-status {
  padding: 12rpx 24rpx;
  border-radius: 20rpx;
  font-size: 24rpx;
}

.status-available {
  background: #e8f5e9;
  color: #4caf50;
}

.status-almost-full {
  background: #fff3e0;
  color: #ff9800;
}

.status-full {
  background: #ffebee;
  color: #f44336;
}
</style>