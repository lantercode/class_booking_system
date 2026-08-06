<template>
  <view class="page">
    <view class="tabs">
      <view
        class="tab-item"
        :class="{ active: activeTab === 'all' }"
        @click="setTab('all')"
      >
        <text>全部</text>
      </view>
      <view
        class="tab-item"
        :class="{ active: activeTab === 'unread' }"
        @click="setTab('unread')"
      >
        <text>未读</text>
        <text class="tab-badge" v-if="unreadCount > 0">{{ unreadCount > 99 ? '99+' : unreadCount }}</text>
      </view>
    </view>

    <view class="notification-list">
      <view
        class="notification-item"
        v-for="item in filteredNotifications"
        :key="item.id"
        :class="{ unread: !item.read }"
        @click="handleRead(item)"
      >
        <view class="notification-left">
          <view class="notification-icon" :class="item.type">
            <text>{{ getIcon(item.type) }}</text>
          </view>
        </view>
        <view class="notification-content">
          <view class="notification-header">
            <text class="notification-title">{{ item.title }}</text>
            <text class="notification-time">{{ formatTime(item.created_at) }}</text>
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
import { getNotifications, markAsRead, markAllAsRead, clearNotifications, addNotification } from '@/utils/notification'

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

function formatTime(dateStr: string) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 7) return `${days}天前`
  return `${date.getMonth() + 1}/${date.getDate()}`
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
  position: relative;
}

.tab-item.active {
  background: #1989fa;
  color: #fff;
}

.tab-badge {
  position: absolute;
  top: -8rpx;
  right: -8rpx;
  background: #f44336;
  color: #fff;
  font-size: 20rpx;
  padding: 2rpx 8rpx;
  border-radius: 20rpx;
  min-width: 36rpx;
}

.notification-list {
  padding: 20rpx 30rpx;
}

.notification-item {
  display: flex;
  align-items: flex-start;
  background: #fff;
  border-radius: 20rpx;
  padding: 30rpx;
  margin-bottom: 20rpx;
  position: relative;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.04);
}

.notification-item.unread {
  background: #f8f9ff;
}

.notification-left {
  margin-right: 20rpx;
}

.notification-icon {
  width: 72rpx;
  height: 72rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32rpx;
}

.notification-icon.booking {
  background: #e3f2fd;
}

.notification-icon.system {
  background: #f3e5f5;
}

.notification-icon.reminder {
  background: #fff3e0;
}

.notification-content {
  flex: 1;
}

.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12rpx;
}

.notification-title {
  font-size: 30rpx;
  font-weight: 500;
  color: #333;
}

.notification-time {
  font-size: 24rpx;
  color: #999;
}

.notification-body {
  font-size: 26rpx;
  color: #666;
  line-height: 1.6;
}

.unread-dot {
  width: 16rpx;
  height: 16rpx;
  background: #f44336;
  border-radius: 50%;
  position: absolute;
  top: 36rpx;
  right: 30rpx;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 120rpx 0;
}

.empty-icon {
  font-size: 80rpx;
  margin-bottom: 20rpx;
}

.empty-text {
  font-size: 28rpx;
  color: #999;
}

.action-bar {
  position: fixed;
  bottom: 30rpx;
  left: 30rpx;
  right: 30rpx;
  display: flex;
  gap: 20rpx;
}

.action-btn {
  flex: 1;
  text-align: center;
  padding: 24rpx;
  background: #fff;
  border-radius: 30rpx;
  font-size: 28rpx;
  color: #666;
  box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.1);
}

.action-btn:active {
  background: #f5f5f5;
}
</style>