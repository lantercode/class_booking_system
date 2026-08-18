<template>
  <view class="page">
    <view class="tabs">
      <view class="tab-item" :class="{ active: activeTab === 'all' }" @click="setTab('all')">
        <text>全部</text>
      </view>
      <view class="tab-item" :class="{ active: activeTab === 'unread' }" @click="setTab('unread')">
        <text>未读</text>
        <text class="tab-badge" v-if="unreadCount > 0">{{ unreadCount > 99 ? '99+' : unreadCount }}</text>
      </view>
    </view>

    <view class="notification-list">
      <view class="notification-item" v-for="item in filteredNotifications" :key="item.id" :class="{ unread: !item.read }" @click="handleRead(item)">
        <view class="notification-left">
          <view class="notification-icon" :class="item.type">
            <text>{{ getIcon(item.type) }}</text>
          </view>
        </view>
        <view class="notification-content">
          <view class="notification-header">
            <text class="notification-title">{{ item.title }}</text>
            <text class="notification-time">{{ formatRelativeTime(item.created_at) }}</text>
          </view>
          <text class="notification-body">{{ item.content }}</text>
        </view>
        <view class="unread-dot" v-if="!item.read"></view>
      </view>
    </view>

    <view class="empty-state" v-if="filteredNotifications.length === 0">
      <text class="empty-icon">🔔</text>
      <text class="empty-text">{{ activeTab === 'all' ? '暂无通知' : '暂无未读通知' }}</text>
    </view>

    <view class="action-bar" v-if="notifications.length > 0">
      <view class="action-btn" @click="markAllRead">
        <text>全部已读</text>
      </view>
      <view class="action-btn" @click="clearAll">
        <text>清空通知</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getNotifications, markAsRead, markAllAsRead, clearNotifications } from '@/utils/notification'
import { formatRelativeTime } from '@/utils/date'

interface Notification {
  id: string
  title: string
  content: string
  type: 'booking' | 'system' | 'reminder'
  read: boolean
  created_at: string
}

const activeTab = ref('all')
const notifications = ref<Notification[]>([])

onMounted(() => {
  loadNotifications()
})

function loadNotifications() {
  notifications.value = getNotifications()
}

const unreadCount = computed(() => {
  return notifications.value.filter(n => !n.read).length
})

const filteredNotifications = computed(() => {
  if (activeTab.value === 'all') return notifications.value
  return notifications.value.filter(n => !n.read)
})

function setTab(tab: string) {
  activeTab.value = tab
}

function getIcon(type: string) {
  switch (type) {
    case 'booking': return '📋'
    case 'system': return '📢'
    case 'reminder': return '⏰'
    default: return '📌'
  }
}

function handleRead(item: Notification) {
  if (!item.read) {
    markAsRead(item.id)
    item.read = true
  }
}

function markAllRead() {
  markAllAsRead()
  loadNotifications()
  uni.showToast({ title: '已全部标记为已读', icon: 'success' })
}

function clearAll() {
  uni.showModal({
    title: '确认清空',
    content: '确定要清空所有通知吗？',
    success: (res) => {
      if (res.confirm) {
        clearNotifications()
        loadNotifications()
        uni.showToast({ title: '已清空', icon: 'success' })
      }
    }
  })
}
</script>

<style lang="scss" scoped>
// ✨ 通知中心 - 高级轻奢风格升级

.page {
  min-height: 100vh;
  background: $bg-primary;                 // ✅ 米白背景（替代#f5f5f5）
  padding-bottom: 120rpx;
}

// 📑 标签栏 - 玻璃态设计
.tabs {
  display: flex;
  background: rgba(255, 255, 255, 0.85);   // ✅ 半透明白色
  backdrop-filter: blur(10rpx);
  padding: $space-md $space-lg;

  & > view {
    margin-right: $space-sm;
  }

  & > view:last-child {
    margin-right: 0;
  }
}

// 🏷️ 标签按钮 - 胶囊式设计
.tab-item {
  flex: 1;
  text-align: center;
  padding: $space-sm $space-md;
  @include text-body;
  color: $text-secondary;                  // ✅ 替代#666
  border-radius: $radius-full;
  background: rgba(201, 166, 107, 0.08);   // ✅ 香槟金浅色背景
  position: relative;
  transition: background $duration-fast $ease-standard,
              color $duration-fast $ease-standard,
              transform $duration-fast $ease-standard;

  &:active {
    transform: scale(0.97);
  }

  &.active {
    background: $primary-gradient;         // ✅ 品牌渐变（替代#1989fa）
    color: #fff;
    box-shadow: $shadow-sm;
  }
}

// 🔴 未读数量徽章
.tab-badge {
  position: absolute;
  top: -8rpx;
  right: -8rpx;
  background: $accent-solid;               // ✅ 莫兰迪粉（替代#f44336）
  color: #fff;
  @include text-overline;
  padding: 2rpx $space-xs;
  border-radius: $radius-full;
  min-width: 36rpx;
}

// 📋 通知列表
.notification-list {
  padding: $space-md $space-lg;
}

// 💬 通知卡片 - 高级卡片设计
.notification-item {
  display: flex;
  align-items: flex-start;
  background: $card-background;            // ✅ 卡片背景（替代#fff）
  border-radius: $radius-lg;               // ✅ 统一圆角
  padding: $space-lg;
  margin-bottom: $space-md;
  position: relative;
  box-shadow: $shadow-card;
  transition: transform $duration-fast $ease-standard,
              box-shadow $duration-fast $ease-standard;

  &:active {
    transform: translateY(-2rpx);
    box-shadow: $shadow-card-hover;   // ✅ 使用已定义的变量（替代$shadow-hover）
  }

  &.unread {
    background: linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.95),
      rgba(232, 213, 196, 0.15)           // ✅ 暖色调未读标记
    );
    border-left: 4rpx solid $primary-solid; // ✅ 左侧品牌色边框
  }
}

.notification-left {
  margin-right: $space-md;
}

// 🔔 通知图标 - 圆形设计
.notification-icon {
  width: 72rpx;
  height: 72rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32rpx;
  flex-shrink: 0;

  &.booking {
    background: linear-gradient(
      135deg,
      rgba(201, 166, 107, 0.15),          // ✅ 香槟金浅色
      rgba(217, 167, 176, 0.1)
    );
    color: $primary-solid;
  }

  &.system {
    background: linear-gradient(
      135deg,
      rgba(217, 167, 176, 0.12),          // ✅ 莫兰迪粉浅色
      rgba(201, 166, 107, 0.08)
    );
    color: $accent-solid;
  }

  &.reminder {
    background: linear-gradient(
      135deg,
      rgba(212, 165, 116, 0.18),          // ✅ 暖金浅色
      rgba(235, 216, 196, 0.1)
    );
    color: #D4A574;
  }
}

.notification-content {
  flex: 1;
  min-width: 0;                           // 允许文本截断
}

.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: $space-xs;
}

.notification-title {
  @include text-h3;
  color: $text-primary;                   // ✅ 替代#333
  line-height: 1.4;
}

.notification-time {
  @include text-caption;
  color: $text-tertiary;                  // ✅ 替代#999
  white-space: nowrap;
}

.notification-body {
  @include text-body;
  color: $text-secondary;                 // ✅ 替代#666
  line-height: 1.6;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

// 🔴 未读红点
.unread-dot {
  width: 16rpx;
  height: 16rpx;
  background: $accent-solid;              // ✅ 替代#f44336
  border-radius: 50%;
  position: absolute;
  top: 36rpx;
  right: 30rpx;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.7;
    transform: scale(1.1);
  }
}

// 📭 空状态
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 120rpx 0;
}

.empty-icon {
  font-size: 80rpx;
  margin-bottom: $space-md;
  opacity: 0.6;
}

.empty-text {
  @include text-body;
  color: $text-tertiary;                  // ✅ 替代#999
}

// ⚡ 操作栏 - 固定底部
.action-bar {
  position: fixed;
  bottom: 30rpx;
  left: 30rpx;
  right: 30rpx;
  display: flex;

  & > view {
    margin-right: $space-sm;
  }

  & > view:last-child {
    margin-right: 0;
  }
}

// 🔘 操作按钮 - 玻璃态设计
.action-btn {
  flex: 1;
  text-align: center;
  padding: $space-md;
  background: rgba(255, 255, 255, 0.9);   // ✅ 半透明背景
  backdrop-filter: blur(10rpx);
  border-radius: $radius-lg;
  @include text-body;
  color: $text-primary;                   // ✅ 替代#666
  box-shadow: $shadow-card;
  transition: background $duration-fast $ease-standard,
              transform $duration-fast $ease-standard;

  &:active {
    background: rgba(245, 237, 228, 0.9); // ✅ 暖灰色点击反馈
    transform: scale(0.98);
  }
}
</style>
ENDOFFILE