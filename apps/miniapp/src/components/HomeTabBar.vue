<template>
  <view class="tab-bar">
    <view
      class="tab-item"
      :class="{ active: currentRoute === 'home' }"
      @tap="goTo('/pages/student/courses/index')"
    >
      <AppIcon
        name="tab-home"
        :size="48"
        :color="currentRoute === 'home' ? '#8b7355' : '#999'"
      />
      <text class="tab-text" :class="{ active: currentRoute === 'home' }"
        >首页</text
      >
      <view v-if="currentRoute === 'home'" class="tab-indicator" />
    </view>
    <view
      class="tab-item"
      :class="{ active: currentRoute === 'schedule' }"
      @tap="goTo('/pages/student/schedule/index')"
    >
      <AppIcon
        name="tab-booking"
        :size="48"
        :color="currentRoute === 'schedule' ? '#8b7355' : '#999'"
      />
      <text class="tab-text" :class="{ active: currentRoute === 'schedule' }"
        >排期</text
      >
      <view v-if="currentRoute === 'schedule'" class="tab-indicator" />
    </view>
    <view
      class="tab-item"
      :class="{ active: currentRoute === 'profile' }"
      @tap="goTo('/pages/student/profile/index')"
    >
      <AppIcon
        name="tab-profile"
        :size="48"
        :color="currentRoute === 'profile' ? '#8b7355' : '#999'"
      />
      <text class="tab-text" :class="{ active: currentRoute === 'profile' }"
        >我的</text
      >
      <view v-if="currentRoute === 'profile'" class="tab-indicator" />
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from "vue";
import AppIcon from "./AppIcon.vue";

const props = defineProps<{
  currentRoute?: string;
}>();

const currentRoute = computed(() => {
  if (!props.currentRoute) return "";

  const routeMap: Record<string, string> = {
    "/pages/student/courses/index": "home",
    "/pages/student/courses/detail": "home",
    "/pages/student/bookings/index": "booking",
    "/pages/student/profile/index": "profile",
    "/pages/student/profile/edit": "profile",
    "/pages/student/profile/settings": "profile",
  };

  return routeMap[props.currentRoute] || "";
});

const goTo = (url: string) => {
  const pages = getCurrentPages();
  const currentPage = pages[pages.length - 1];

  const targetRoute = url.replace(/^\//, "").replace(/\/index$/, "");

  if (currentPage && currentPage.route === targetRoute) {
    return;
  }

  uni.redirectTo({ url, animationType: "fade-in", animationDuration: 250 });
};
</script>

<style lang="scss">
.tab-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  background: #fff;
  padding: 12rpx 0 28rpx;
  border-top: 1rpx solid #f5f5f5;
  box-shadow: 0 -2rpx 12rpx rgba(0, 0, 0, 0.04);
}

.tab-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  padding: 8rpx 0;
}

.tab-text {
  font-size: 22rpx;
  color: #999;
  margin-top: 6rpx;
  transition: color 0.3s ease;

  &.active {
    color: #8b7355;
    font-weight: 500;
  }
}

.tab-indicator {
  position: absolute;
  bottom: 0;
  width: 40rpx;
  height: 4rpx;
  background: linear-gradient(90deg, #c9a66b, #d9a7b0);
  border-radius: 2rpx;
}
</style>
