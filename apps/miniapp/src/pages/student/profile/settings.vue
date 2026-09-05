<template>
  <view class="container">
    <!-- <view class="header">
      <view class="back-btn" @tap="goBack">
        <text class="back-icon">←</text>
      </view>
      <text class="header-title">设置</text>
      <view class="placeholder"></view>
    </view> -->

    <view class="menu-list">
      <view class="menu-item" @tap="handleUnbindWechat">
        <view class="menu-icon">🔗</view>
        <text class="menu-text">解绑微信</text>
        <text class="menu-arrow">→</text>
      </view>
      <view class="menu-item">
        <view class="menu-icon">🔔</view>
        <text class="menu-text">消息通知</text>
        <switch class="menu-switch" :checked="notificationsEnabled" @change="toggleNotifications" />
      </view>
      <view class="menu-item">
        <view class="menu-icon">🔐</view>
        <text class="menu-text">修改密码</text>
        <text class="menu-arrow">→</text>
      </view>
      <view class="menu-item" @tap="goToAbout">
        <view class="menu-icon">ℹ️</view>
        <text class="menu-text">关于我们</text>
        <text class="menu-arrow">→</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { navigateTo } from '@/utils/navigation'
import { wechatUnbind } from '@/utils/wechat'
import { clearAuthData } from '@/api'

const notificationsEnabled = ref(true)

const toggleNotifications = (e: any) => {
  notificationsEnabled.value = e.detail.value
  uni.showToast({
    title: notificationsEnabled.value ? '已开启通知' : '已关闭通知',
    icon: 'none'
  })
}

const handleUnbindWechat = () => {
  uni.showModal({
    title: '解绑微信',
    content: '解绑后您将退出当前登录状态，需重新通过手机号登录。确定要解绑吗？',
    confirmText: '确定解绑',
    cancelText: '取消',
    confirmColor: '#e74c3c',
    success: async (res) => {
      if (res.confirm) {
        uni.showLoading({ title: '解绑中...', mask: true })
        const result = await wechatUnbind()
        uni.hideLoading()
        if (result.success) {
          console.log('🔓 微信解绑成功，开始清除本地登录态...')

          // 🆕 设置"刚解绑"标志，防止刷新后自动登录
          uni.setStorageSync('just_unbound_wechat', 'true')
          console.log('✅ 已设置 just_unbound_wechat 标志')

          clearAuthData()

          console.log('✅ 本地存储已清除，当前状态:')
          console.log('  - token:', uni.getStorageSync('token') || '(空)')
          console.log('  - refresh_token:', uni.getStorageSync('refresh_token') || '(空)')
          console.log('  - user_role:', uni.getStorageSync('user_role') || '(空)')
          console.log('  - tenant_slug:', uni.getStorageSync('tenant_slug') || '(空)')
          console.log('  - just_unbound_wechat:', uni.getStorageSync('just_unbound_wechat') || '(空)')

          uni.showToast({ title: '微信已解绑', icon: 'success', duration: 1500 })
          setTimeout(() => {
            console.log('🚀 准备跳转到首页...')
            uni.reLaunch({
              url: '/pages/index/index',
              complete: () => {
                console.log('✅ 跳转完成')
              },
              fail: (err: any) => {
                console.error('❌ 跳转失败:', err)
              }
            })
          }, 1500)
        } else {
          uni.showToast({ title: result.msg, icon: 'none' })
        }
      }
    }
  })
}

const goBack = () => {
  uni.navigateBack()
}

const goToAbout = () => {
  navigateTo({ url: '/pages/student/profile/about' })
}
</script>

<style lang="scss">
// ✨ 设置页面 - 高级轻奢风格升级

.container {
  min-height: 100vh;
  background: $bg-primary;                 // ✅ 米白背景（替代#f5f5f5）
}

// 🎯 头部区域
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

// ⬅️ 返回按钮
.back-btn {
  width: 64rpx;
  height: 64rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: background $duration-fast $ease-standard,
              transform $duration-fast $ease-standard;

  &:active {
    background: rgba(201, 166, 107, 0.1); // ✅ 品牌色点击反馈
    transform: scale(0.95);
  }
}

.back-icon {
  font-size: 40rpx;
  color: $text-primary;
}

.header-title {
  @include text-h1; // ✅ 使用Design System字体
  color: $text-primary;
}

.placeholder {
  width: 64rpx;
}

// 📋 菜单列表 - 高级卡片设计
.menu-list {
  background: $card-background;            // ✅ 卡片背景（替代#fff）
  border-radius: $radius-lg;              // ✅ 统一圆角（替代16rpx）
  overflow: hidden;
  box-shadow: $shadow-card;               // ✅ 添加阴影
}

// 📝 菜单项
.menu-item {
  display: flex;
  align-items: center;
  padding: $space-lg $space-lg;           // ✅ 统一间距
  border-bottom: 1rpx solid $border-light;
  transition: background $duration-fast $ease-standard;

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

.menu-switch {
  transform: scale(0.8);
}
</style>