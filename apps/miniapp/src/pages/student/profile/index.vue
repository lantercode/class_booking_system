<template>
  <view class="profile_container">

    <!-- 自定义导航栏 - 参照课程列表页面 -->
    <AppNavbar
      title=""
      :show-back="false"
      variant="default"
    >
      <template #left>
        <view>我的</view>
      </template>
    </AppNavbar>

    <!-- 沉浸式个人信息区 -->
    <view class="profile-header-immersive">
      <view class="profile-header-content">
        <view class="avatar-wrapper">
          <view class="avatar">
            <text class="avatar-text">{{ userInfo?.nickname?.charAt(0) || '?' }}</text>
          </view>
        </view>
        <view class="user-info">
          <text class="user-name">{{ userInfo?.nickname || '学员' }}</text>
          <text class="user-role">学员</text>
        </view>
        <view class="edit-btn" @tap="goToEdit">
          <text>编辑</text>
        </view>
      </view>
    </view>

    <view class="menu-list">
      <view class="menu-item" @tap="goToBookings">
        <view class="menu-icon">📝</view>
        <text class="menu-text">预约记录</text>
        <text class="menu-arrow">→</text>
      </view>
      <view class="menu-item" @tap="goToMembership">
        <view class="menu-icon">💳</view>
        <text class="menu-text">我的会员卡</text>
        <text class="menu-arrow">→</text>
      </view>
      <view class="menu-item" @tap="goToSettings">
        <view class="menu-icon">⚙️</view>
        <text class="menu-text">设置</text>
        <text class="menu-arrow">→</text>
      </view>
      <view class="menu-item" @tap="handleLogout">
        <view class="menu-icon">🚪</view>
        <text class="menu-text">退出登录</text>
        <text class="menu-arrow">→</text>
      </view>
    </view>

    <StudentTabBar currentRoute="/pages/student/profile/index" />

    <!-- AI 智能助手 -->
    <AiAssistant
      :session-id="'student_' + (userId || 'default')"
    />
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { studentApi } from '@/api'
import { checkLogin, logout } from '@/utils/auth'
import StudentTabBar from '@/components/StudentTabBar.vue'
import AiAssistant from '@/components/AiAssistant.vue'
import { navigateTo } from '@/utils/navigation'
import AppNavbar from '@/components/AppNavbar.vue'

const userInfo = ref<any>(null)
const userId = ref('')

// ✅ 页面卸载标记
let isUnmounted = false

onMounted(() => {
  console.log('\n ===== 学员"我的"页面 - onMounted 触发 =====\n')

  if (!checkLogin('student')) return

  loadUserInfo()
})

onUnmounted(() => {
  isUnmounted = true
})

const loadUserInfo = () => {
  const info = uni.getStorageSync('user_info')
  if (info) {
    const parsed = JSON.parse(info)
    userInfo.value = parsed
    userId.value = parsed.id || ''
    console.log('✅ 用户信息已加载:', parsed?.nickname || '未知')
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
  navigateTo({ url: '/pages/student/profile/edit' })
}

const goToMembership = () => {
  navigateTo({ url: '/pages/student/membership/index' })
}

const goToSettings = () => {
  navigateTo({ url: '/pages/student/profile/settings' })
}

const goToCourses = () => {
  navigateTo({ url: '/pages/student/courses/index' })
}

const goToBookings = () => {
  navigateTo({ url: '/pages/student/bookings/index' })
}

</script>

<style lang="scss">
.profile_container {
  @include page-container($gradient-page);  // ✅ 使用统一的Mixin，保留渐变背景
}

// ✨ 沉浸式个人信息区 - 多层次高级设计（告别单调渐变）
.profile-header-immersive {
  // 🎨 第一层：基础渐变（主色调）- 个人中心专属配色
  background: 
    radial-gradient(
      ellipse at 25% 60%,                    // 左下侧光斑（温暖感）
      rgba(217, 167, 176, 0.16) 0%,
      transparent 55%
    ),
    radial-gradient(
      ellipse at 85% 15%,                    // 右上角光斑（高级感）
      rgba(201, 166, 107, 0.2) 0%,
      transparent 48%
    ),
    linear-gradient(
      170deg,                                // 更柔和的角度
      #D4A574 0%,                            // 深香槟金起点
      #E0C4A8 25%,                           // 暖金过渡
      #EBD9CC 55%,                           // 玫瑰米色
      #F8F2ED 100%                           // 近白色终点（更温暖）
    );

  position: relative;
  overflow: hidden;
  margin: 0;                                 // ✅ 完全去除外边距（上下左右）
  padding: 0;                               // ✅ 去除内边距，由子元素控制
  width: 100%;                               // ✅ 占满父容器宽度
  min-width: 100vw;                         // ✅ 最小宽度为屏幕宽度

  // ✨ 第二层：动态光晕装饰（右上角）
  &::before {
    content: '';
    position: absolute;
    top: -40rpx;
    right: -70rpx;
    width: 300rpx;
    height: 300rpx;
    background: radial-gradient(
      circle,
      rgba(201, 166, 107, 0.22) 0%,
      rgba(217, 167, 176, 0.12) 35%,
      transparent 70%
    );
    border-radius: 50%;
    filter: blur(45rpx);
    animation: gentleFloat 11s ease-in-out infinite;
    pointer-events: none;
  }

  // 💫 第三层：底部装饰线（精致细节）
  &::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 3rpx;                           // 稍微粗一点
    background: linear-gradient(
      90deg,
      transparent 0%,
      rgba(201, 166, 107, 0.3) 20%,
      rgba(217, 167, 176, 0.4) 50%,         // 中间莫兰迪粉
      rgba(201, 166, 107, 0.3) 80%,
      transparent 100%
    );

    // 底部额外光晕效果
    box-shadow: 0 2rpx 12rpx rgba(201, 166, 107, 0.15);
  }
}

// 🌊 缓慢浮动动画（个人中心专用 - 更柔和的节奏）
@keyframes gentleFloat {
  0%, 100% {
    transform: translate(0, 0) scale(1);
    opacity: 0.7;
  }
  33% {
    transform: translate(-18rpx, 14rpx) scale(1.06);
    opacity: 0.85;
  }
  66% {
    transform: translate(14rpx, -10rpx) scale(0.96);
    opacity: 0.72;
  }
}

// ✅ 注意：状态栏占位已由 AppNavbar 统一处理
// 此处不再需要单独的 status-bar-placeholder

.profile-header-content {
  display: flex;
  align-items: center;                      // 垂直居中对齐
  justify-content: space-between;           // 水平两端对齐（头像左，编辑右）
  position: relative;
  z-index: 1;

  // 关键优化：增大最小高度，防止按钮被遮挡
  min-height: 260rpx;                       // 最小高度
  width: 100%;                               // 占满容器宽度
  box-sizing: border-box;                   // 边框盒模型
  padding: $space-lg $space-md;                 // 内边距，保证内容不贴边
}

.avatar-wrapper {
  margin-right: $space-md;
}

.avatar {
  width: 120rpx;
  height: 120rpx;
  border-radius: $radius-full;
  background: rgba(255, 255, 255, 0.25);  // ✅ 更新：半透明白色背景
  backdrop-filter: blur(10rpx);
  -webkit-backdrop-filter: blur(10rpx);
  border: 2rpx solid rgba(255, 255, 255, 0.3);   // 新增：白色边框
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.1);     // 新增：阴影效果
}

.avatar-text {
  font-size: $font-size-h2;
  color: #fff;
  font-weight: $font-weight-bold;
}

.user-info {
  flex: 1;
}

.user-name {
  font-size: $font-size-h3;
  font-weight: $font-weight-bold;
  color: #fff;
  display: block;
  margin-bottom: $space-2xs;
  letter-spacing: $letter-spacing-tight;
}

.user-role {
  font-size: $font-size-body_sm;
  color: rgba(255, 255, 255, 0.85);
  font-weight: $font-weight-medium;
}

.edit-btn {
  padding: $space-xs $space-md;
  background: rgba(255, 255, 255, 0.25);  // ✅ 更新：更透明的背景
  backdrop-filter: blur(10rpx);
  -webkit-backdrop-filter: blur(10rpx);
  border: 1rpx solid rgba(255, 255, 255, 0.3);   // 新增：边框
  border-radius: $radius-2xl;
  transition: transform $duration-fast $ease-standard,
              box-shadow $duration-fast $ease-standard,
              opacity $duration-fast $ease-standard;

  &:active {
    background: rgba(255, 255, 255, 0.35);
    transform: scale(0.96);
  }

  text {
    font-size: $font-size-body_sm;
    color: #fff;
    font-weight: $font-weight-medium;
  }
}

.menu-list {
  background: rgba(255, 255, 255, 0.95);   // ✅ 更新：玻璃态背景
  backdrop-filter: blur(20rpx);
  -webkit-backdrop-filter: blur(20rpx);
  margin: $space-lg $space-lg $space-lg;
  border-radius: $radius-lg;            // ✅ 更新：使用圆角系统
  overflow: hidden;
  box-shadow: $shadow-card;             // ✅ 更新：使用阴影系统
  border: 1rpx solid $border-subtle;
  transition: background $duration-fast $ease-standard,
              transform $duration-fast $ease-standard,
              box-shadow $duration-fast $ease-standard;

  &:active {
    transform: translateY(-2rpx);
    box-shadow: $shadow-card-hover;
  }
}

.menu-item {
  display: flex;
  align-items: center;
  padding: $space-md $space-lg;
  border-bottom: 1rpx solid $border-subtle;
  transition: background $duration-fast $ease-standard;

  &:last-child {
    border-bottom: none;
  }

  &:active {
    background: $bg-tertiary;           // ✅ 更新：点击反馈背景
  }
}

.menu-icon {
  font-size: $icon-size-md;
  margin-right: $space-md;
  width: 48rpx;                        // 新增：固定宽度，保持对齐
  text-align: center;
}

.menu-text {
  flex: 1;
  font-size: $font-size-body;
  color: $text-primary;                // ✅ 更新：使用文本变量
  font-weight: $font-weight-medium;
  letter-spacing: $letter-spacing-tight;
}

.menu-arrow {
  font-size: $font-size-body_sm;
  color: $text-tertiary;
  transition: transform $duration-fast $ease-standard,
              color $duration-fast $ease-standard;

  .menu-item:active & {
    transform: translateX(4rpx);        // 点击时向右移动
  }
}

.tab-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  background: rgba(255, 255, 255, 0.98);   // ✅ 更新：近白色背景
  backdrop-filter: blur(20rpx);
  -webkit-backdrop-filter: blur(20rpx);
  padding: $space-sm 0 $space-2xl;
  border-top: 1rpx solid $border-light;     // ✅ 更新：使用边框变量
  box-shadow: 0 -4rpx 16rpx rgba(26, 26, 26, 0.04);  // ✅ 新增：顶部阴影
}

.tab-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;

  &.active {
    .tab-icon, .tab-text {
      color: $primary-solid;            // ✅ 更新：香槟金色
    }
  }
}

.tab-icon {
  font-size: $icon-size-md;
  margin-bottom: $space-2xs;
  color: $text-tertiary;
  transition: color $duration-fast $ease-standard;
}

.tab-text {
  font-size: $font-size-caption;
  color: $text-tertiary;
  transition: color $duration-fast $ease-standard;
}
</style>