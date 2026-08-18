<template>
  <view class="tab-bar">
    <view 
      class="tab-item" 
      :class="{ active: currentRoute === 'courses' }"
      @tap="goTo('/pages/student/courses/index')"
    >
      <text class="tab-icon">📚</text>
      <text class="tab-text">课程</text>
    </view>
    <view 
      class="tab-item" 
      :class="{ active: currentRoute === 'schedule' }"
      @tap="goTo('/pages/student/schedule/index')"
    >
      <text class="tab-icon">📅</text>
      <text class="tab-text">排期</text>
    </view>
    <view 
      class="tab-item" 
      :class="{ active: currentRoute === 'bookings' }"
      @tap="goTo('/pages/student/bookings/index')"
    >
      <text class="tab-icon">📝</text>
      <text class="tab-text">预约</text>
    </view>
    <view 
      class="tab-item" 
      :class="{ active: currentRoute === 'profile' }"
      @tap="goTo('/pages/student/profile/index')"
    >
      <text class="tab-icon">👤</text>
      <text class="tab-text">我的</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  currentRoute?: string
}>()

const currentRoute = computed(() => {
  if (!props.currentRoute) return ''
  
  const routeMap: Record<string, string> = {
    '/pages/student/courses/index': 'courses',
    '/pages/student/courses/detail': 'courses',
    '/pages/student/schedule/index': 'schedule',
    '/pages/student/bookings/index': 'bookings',
    '/pages/student/profile/index': 'profile',
    '/pages/student/profile/edit': 'profile',
    '/pages/student/profile/settings': 'profile'
  }
  
  return routeMap[props.currentRoute] || ''
})

const goTo = (url: string) => {
  const pages = getCurrentPages()
  const currentPage = pages[pages.length - 1]
  
  const targetRoute = url.replace(/^\//, '').replace(/\/index$/, '')
  
  if (currentPage && currentPage.route === targetRoute) {
    return
  }
  
  uni.redirectTo({ url, animationType: 'fade-in', animationDuration: 250 })
}
</script>

<style lang="scss">
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