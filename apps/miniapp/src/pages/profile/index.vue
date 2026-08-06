<template>
  <view class="page">
    <view class="profile-header">
      <view class="avatar-area">
        <view class="avatar">
          <text class="avatar-icon">👤</text>
        </view>
        <view class="user-info">
          <text class="user-name">{{ userInfo.nickname || '点击登录' }}</text>
          <text class="user-role">{{ userInfo.role === 'teacher' ? '教师' : '学员' }}</text>
        </view>
      </view>
      <view class="login-btn" v-if="!isLoggedIn" @click="goToLogin">
        <text>登录</text>
      </view>
    </view>

    <view class="stats-card">
      <view class="stat-item">
        <text class="stat-value">{{ stats.totalCourses }}</text>
        <text class="stat-label">课程数</text>
      </view>
      <view class="stat-divider"></view>
      <view class="stat-item">
        <text class="stat-value">{{ stats.totalBookings }}</text>
        <text class="stat-label">预约数</text>
      </view>
      <view class="stat-divider"></view>
      <view class="stat-item">
        <text class="stat-value">{{ stats.totalSchedules }}</text>
        <text class="stat-label">排期数</text>
      </view>
    </view>

    <view class="menu-list">
      <view class="menu-item" @click="goToBookings">
        <text class="menu-icon">📋</text>
        <text class="menu-text">我的预约</text>
        <text class="menu-arrow">›</text>
      </view>
      <view class="menu-item" @click="goToSchedule">
        <text class="menu-icon">📅</text>
        <text class="menu-text">我的课表</text>
        <text class="menu-arrow">›</text>
      </view>
      <view class="menu-item" @click="goToCourses">
        <text class="menu-icon">📚</text>
        <text class="menu-text">课程中心</text>
        <text class="menu-arrow">›</text>
      </view>
      <view class="menu-item" @click="handleEditProfile">
        <text class="menu-icon">✏️</text>
        <text class="menu-text">编辑资料</text>
        <text class="menu-arrow">›</text>
      </view>
      <view class="menu-item" @click="handleSettings">
        <text class="menu-icon">⚙️</text>
        <text class="menu-text">设置</text>
        <text class="menu-arrow">›</text>
      </view>
    </view>

    <view class="logout-area" v-if="isLoggedIn">
      <view class="logout-btn" @click="handleLogout">
        <text>退出登录</text>
      </view>
    </view>

    <view class="version-info">
      <text>版本号：v1.0.0</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { teacherApi, courseApi, scheduleApi, bookingApi } from '@/api'

const userInfo = ref({
  nickname: '',
  role: 'student'
})

const isLoggedIn = ref(false)

const stats = ref({
  totalCourses: 0,
  totalBookings: 0,
  totalSchedules: 0
})

onMounted(() => {
  loadUserInfo()
  loadStats()
})

async function loadUserInfo() {
  try {
    const token = uni.getStorageSync('token')
    if (token) {
      const res = await teacherApi.getInfo()
      userInfo.value = {
        nickname: res.data.nickname || '用户',
        role: res.data.role || 'student'
      }
      isLoggedIn.value = true
    }
  } catch (e) {
    console.error('加载用户信息失败', e)
    isLoggedIn.value = false
  }
}

async function loadStats() {
  try {
    const [cRes, sRes, bRes] = await Promise.all([
      courseApi.list({ page_size: 500 }),
      scheduleApi.list({ page_size: 500 }),
      bookingApi.list({ page_size: 500 })
    ])
    stats.value = {
      totalCourses: cRes.data.total || 0,
      totalBookings: bRes.data.total || 0,
      totalSchedules: sRes.data.total || 0
    }
  } catch (e) {
    console.error('加载统计数据失败', e)
  }
}

function goToLogin() {
  uni.navigateTo({ url: '/pages/login/index' })
}

function goToBookings() {
  uni.switchTab({ url: '/pages/booking/list' })
}

function goToSchedule() {
  uni.switchTab({ url: '/pages/schedule/index' })
}

function goToCourses() {
  uni.switchTab({ url: '/pages/course/list' })
}

function handleEditProfile() {
  uni.showToast({ title: '功能开发中', icon: 'none' })
}

function handleSettings() {
  uni.showToast({ title: '功能开发中', icon: 'none' })
}

function handleLogout() {
  uni.showModal({
    title: '提示',
    content: '确定要退出登录吗？',
    success: (res) => {
      if (res.confirm) {
        uni.removeStorageSync('token')
        uni.removeStorageSync('refresh_token')
        userInfo.value = { nickname: '', role: 'student' }
        isLoggedIn.value = false
        uni.showToast({ title: '退出成功', icon: 'success' })
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

.profile-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 60rpx 30rpx 40rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.avatar-area {
  display: flex;
  align-items: center;
  gap: 24rpx;
}

.avatar {
  width: 100rpx;
  height: 100rpx;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-icon {
  font-size: 48rpx;
}

.user-info {
  display: flex;
  flex-direction: column;
}

.user-name {
  font-size: 36rpx;
  font-weight: bold;
  color: #fff;
}

.user-role {
  font-size: 24rpx;
  color: rgba(255, 255, 255, 0.8);
  margin-top: 8rpx;
}

.login-btn {
  padding: 16rpx 32rpx;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 30rpx;
  font-size: 28rpx;
  color: #fff;
}

.stats-card {
  display: flex;
  justify-content: space-around;
  margin: -30rpx 30rpx 20rpx;
  background: #fff;
  border-radius: 20rpx;
  padding: 30rpx;
  box-shadow: 0 8rpx 32rpx rgba(0, 0, 0, 0.1);
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-value {
  font-size: 40rpx;
  font-weight: bold;
  color: #333;
}

.stat-label {
  font-size: 24rpx;
  color: #999;
  margin-top: 8rpx;
}

.stat-divider {
  width: 2rpx;
  background: #f0f0f0;
}

.menu-list {
  margin: 20rpx 30rpx;
  background: #fff;
  border-radius: 20rpx;
  overflow: hidden;
}

.menu-item {
  display: flex;
  align-items: center;
  padding: 30rpx;
  border-bottom: 2rpx solid #f5f5f5;
  
  &:last-child {
    border-bottom: none;
  }
  
  &:active {
    background: #f9f9f9;
  }
}

.menu-icon {
  font-size: 36rpx;
  margin-right: 20rpx;
}

.menu-text {
  flex: 1;
  font-size: 30rpx;
  color: #333;
}

.menu-arrow {
  font-size: 36rpx;
  color: #ccc;
}

.logout-area {
  margin: 20rpx 30rpx;
}

.logout-btn {
  width: 100%;
  padding: 28rpx;
  background: #fff;
  border-radius: 30rpx;
  text-align: center;
  font-size: 30rpx;
  color: #f44336;
  border: 2rpx solid #ffebee;
}

.version-info {
  text-align: center;
  padding: 40rpx;
  font-size: 24rpx;
  color: #999;
}
</style>