<template>
  <view class="container">
    <view class="profile-header">
      <view class="avatar-wrapper">
        <view class="avatar">
          <text class="avatar-text">{{ userInfo?.nickname?.charAt(0) || '?' }}</text>
        </view>
      </view>
      <view class="user-info">
        <text class="user-name">{{ userInfo?.nickname || '教师' }}</text>
        <text class="user-role">教师</text>
      </view>
      <view class="edit-btn" @tap="goToEdit">
        <text>编辑</text>
      </view>
    </view>

    <view class="stats-card">
      <view class="stat-item">
        <text class="stat-value">{{ stats.courses || 0 }}</text>
        <text class="stat-label">课程数</text>
      </view>
      <view class="stat-divider"></view>
      <view class="stat-item">
        <text class="stat-value">{{ stats.schedules || 0 }}</text>
        <text class="stat-label">排期数</text>
      </view>
      <view class="stat-divider"></view>
      <view class="stat-item">
        <text class="stat-value">{{ stats.students || 0 }}</text>
        <text class="stat-label">学员数</text>
      </view>
    </view>

    <view class="menu-list">
      <view class="menu-item" @tap="goToBookingHistory">
        <view class="menu-icon">📅</view>
        <text class="menu-text">预约记录</text>
        <text class="menu-arrow">→</text>
      </view>
      <view class="menu-item" @tap="goToMyWallet">
        <view class="menu-icon">💰</view>
        <text class="menu-text">我的钱包</text>
        <text class="menu-arrow">→</text>
      </view>
      <view class="menu-item" @tap="goToSettings">
        <view class="menu-icon">⚙️</view>
        <text class="menu-text">设置</text>
        <text class="menu-arrow">→</text>
      </view>
    </view>

    <view class="menu-list">
      <view class="menu-item" @tap="handleLogout">
        <view class="menu-icon">🚪</view>
        <text class="menu-text">退出登录</text>
        <text class="menu-arrow">→</text>
      </view>
    </view>

    <TeacherTabBar currentRoute="/pages/teacher/profile/index" />
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { teacherApi } from '@/api'
import TeacherTabBar from '@/components/TeacherTabBar.vue'
import { checkLogin, logout } from '@/utils/auth'

const userInfo = ref<any>(null)
const stats = ref({
  courses: 0,
  schedules: 0,
  students: 0
})

onMounted(() => {
  if (!checkLogin('teacher')) return
  loadUserInfo()
  loadStats()
})

const loadUserInfo = () => {
  const info = uni.getStorageSync('user_info')
  if (info) {
    userInfo.value = JSON.parse(info)
  }
}

const loadStats = async () => {
  try {
    const result = await teacherApi.getStats()
    stats.value = result.data
  } catch {
    console.error('Failed to load stats')
  }
}

const handleLogout = () => {
  uni.showModal({
    title: '确认退出',
    content: '确定要退出登录吗？',
    success: (res) => {
      if (res.confirm) {
        logout()
      }
    }
  })
}

const goToEdit = () => {
  uni.navigateTo({ url: '/pages/teacher/profile/edit' })
}

const goToBookingHistory = () => {
  uni.navigateTo({ url: '/pages/teacher/profile/history' })
}

const goToMyWallet = () => {
  uni.navigateTo({ url: '/pages/teacher/profile/wallet' })
}

const goToSettings = () => {
  uni.navigateTo({ url: '/pages/teacher/profile/settings' })
}

const goToCourses = () => {
  uni.navigateTo({ url: '/pages/teacher/courses/index' })
}

const goToSchedule = () => {
  uni.navigateTo({ url: '/pages/teacher/schedule/index' })
}

const goToStudents = () => {
  uni.navigateTo({ url: '/pages/teacher/students/index' })
}
</script>

<style lang="scss">
// ✨ 教师个人中心 - 高级轻奢风格升级

.container {
  min-height: 100vh;
  background: $bg-primary;                 // ✅ 米白背景（替代#f5f5f5）
  padding-bottom: 120rpx;
}

// 🎯 沉浸式个人信息区 - 多层次设计（与学员端统一风格）
.profile-header {
  display: flex;
  align-items: center;
  padding: 80rpx $space-lg $space-xl;

  // 🎨 多层背景（教师专属配色 - 更沉稳的香槟金）
  background:
    radial-gradient(
      ellipse at 20% 70%,                  // 左下侧光斑
      rgba(201, 166, 107, 0.18) 0%,
      transparent 55%
    ),
    radial-gradient(
      ellipse at 80% 20%,                  // 右上角光斑
      rgba(180, 140, 100, 0.15) 0%,       // 稍深的金色
      transparent 48%
    ),
    linear-gradient(
      175deg,                              // 角度稍大，更显稳重
      #B8936A 0%,                          // 深香槟金起点
      #C9A66B 30%,                         // 标准金
      #D9C4A8 65%,                         // 浅金
      #EDE4D8 100%                         // 近白色
    );

  position: relative;
  overflow: hidden;

  &::before {                             // 光晕装饰
    content: '';
    position: absolute;
    top: -50rpx;
    right: -60rpx;
    width: 280rpx;
    height: 280rpx;
    background: radial-gradient(
      circle,
      rgba(184, 147, 106, 0.2) 0%,
      rgba(201, 166, 107, 0.12) 40%,
      transparent 70%
    );
    border-radius: 50%;
    filter: blur(45rpx);
    pointer-events: none;
  }

  &::after {                             // 底部装饰线
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 2rpx;
    background: linear-gradient(
      90deg,
      transparent 0%,
      rgba(184, 147, 106, 0.4) 30%,
      rgba(201, 166, 107, 0.35) 50%,
      rgba(184, 147, 106, 0.4) 70%,
      transparent 100%
    );
  }
}

.avatar-wrapper {
  margin-right: $space-md;               // ✅ 统一间距
}

.avatar {
  width: 120rpx;
  height: 120rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.35); // ✅ 稍微增加透明度
  backdrop-filter: blur(10rpx);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.08); // ✅ 增加阴影
}

.avatar-text {
  @include text-display; // ✅ 使用Design System字体
  color: #fff;
  text-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.15); // ✅ 文字阴影增强可读性
}

.user-info {
  flex: 1;
}

.user-name {
  @include text-h1; // ✅ 使用Design System字体
  color: #fff;
  display: block;
  margin-bottom: $space-xs;
  text-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.1);
}

.user-role {
  @include text-body;
  color: rgba(255, 255, 255, 0.85);     // ✅ 稍微提高不透明度
}

.edit-btn {
  padding: $space-sm $space-md;
  background: rgba(255, 255, 255, 0.25); // ✅ 提高背景可见度
  backdrop-filter: blur(10rpx);
  border-radius: $radius-full;
  transition: all $duration-fast $ease-standard;

  &:active {
    background: rgba(255, 255, 255, 0.35);
    transform: scale(0.97);
  }

  text {
    @include text-body;
    color: #fff;
  }
}

// 📊 统计卡片 - 高级设计
.stats-card {
  display: flex;
  align-items: center;
  margin: -40rpx $space-lg $space-lg;
  background: $card-background;            // ✅ 卡片背景（替代#fff）
  border-radius: $radius-xl;              // ✅ 统一圆角（替代20rpx）
  padding: $space-lg;
  box-shadow: $shadow-lg;                 // ✅ 使用已定义的变量（替代$shadow-elevated）

  // 上浮效果
  position: relative;
  z-index: 10;
}

.stat-item {
  flex: 1;
  text-align: center;
}

.stat-value {
  @include text-display;
  color: $primary-solid;                 // ✅ 香槟金（替代#667eea）
  display: block;
  margin-bottom: $space-xs;

  &.highlight {
    color: $accent-solid;                // ✅ 莫兰迪粉用于强调
  }
}

.stat-label {
  @include text-caption;
  color: $text-secondary;                // ✅ 替代#999
}

.stat-divider {
  width: 1rpx;
  height: 60rpx;
  background: linear-gradient(
    to bottom,
    transparent,
    $border-light 50%,
    transparent
  );
}

// 📋 菜单列表 - 高级卡片设计
.menu-list {
  background: $card-background;            // ✅ 卡片背景（替代#fff）
  margin: 0 $space-lg $space-md;
  border-radius: $radius-lg;              // ✅ 统一圆角
  overflow: hidden;
  box-shadow: $shadow-card;               // ✅ 添加阴影
}

.menu-item {
  display: flex;
  align-items: center;
  padding: $space-lg $space-lg;           // ✅ 统一间距
  border-bottom: 1rpx solid $border-light; // ✅ 替代#f5f5f5
  transition: all $duration-fast $ease-standard;

  &:active {
    background: rgba(245, 237, 228, 0.6); // ✅ 暖灰色点击反馈
  }

  &:last-child {
    border-bottom: none;
  }
}

.menu-icon {
  font-size: 40rpx;
  margin-right: $space-md;
  width: 44rpx;                           // 固定宽度，对齐文字
  text-align: center;
}

.menu-text {
  flex: 1;
  @include text-body; // ✅ 使用Design System字体
  color: $text-primary;
}

.menu-arrow {
  @include text-caption;
  color: $text-tertiary;                  // ✅ 替代#ccc
  transition: transform $duration-fast $ease-standard;
}

.menu-item:active .menu-arrow {
  transform: translateX(4rpx);            // 点击时箭头微移动
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