<template>
  <view 
    class="app-avatar" 
    :class="[`avatar-${size}`, { 'avatar-online': online }]"
    @tap="handleTap"
  >
    <!-- 图片头像 -->
    <image 
      v-if="src" 
      :src="src" 
      mode="aspectFill"
      class="avatar-image"
    />
    
    <!-- 文字头像（无图片时显示首字母） -->
    <text v-else-if="name" class="avatar-text">{{ name.charAt(0) }}</text>
    
    <!-- 默认图标 -->
    <text v-else class="avatar-icon">👤</text>

    <!-- 在线状态指示器 -->
    <view v-if="online !== undefined" class="avatar-status" :class="{ 'status-online': online }"></view>
  </view>
</template>

<script setup lang="ts">
interface Props {
  src?: string
  name?: string
  size?: 'sm' | 'md' | 'lg' | 'xl'
  online?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  src: '',
  name: '',
  size: 'md',
  online: undefined
})

const emit = defineEmits<{
  (e: 'tap'): void
}>()

function handleTap() {
  emit('tap')
}
</script>

<style lang="scss" scoped>

.app-avatar {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: $radius-full;
  overflow: hidden;
  background: $primary-gradient;
  flex-shrink: 0;

  // ------------------------------------------
  // 尺寸变体
  // ------------------------------------------
  &.avatar-sm {
    width: $avatar-size-sm;
    height: $avatar-size-sm;

    .avatar-text,
    .avatar-icon {
      font-size: 28rpx;
    }
  }

  &.avatar-md {
    width: $avatar-size-md;
    height: $avatar-size-md;

    .avatar-text,
    .avatar-icon {
      font-size: 36rpx;
    }
  }

  &.avatar-lg {
    width: $avatar-size-lg;
    height: $avatar-size-lg;

    .avatar-text,
    .avatar-icon {
      font-size: 48rpx;
    }
  }

  &.avatar-xl {
    width: $avatar-size-xl;
    height: $avatar-size-xl;

    .avatar-text,
    .avatar-icon {
      font-size: 64rpx;
    }

    // 大头像带边框光晕
    box-shadow: 0 4rpx 16rpx rgba(102, 126, 234, 0.3);
    border: 4rpx solid rgba(255, 255, 255, 0.2);
  }

  // 图片
  .avatar-image {
    width: 100%;
    height: 100%;
  }

  // 文字
  .avatar-text,
  .avatar-icon {
    color: $text-primary;
    font-weight: $font-weight-semibold;
    line-height: 1;
  }

  // 在线状态
  .avatar-status {
    position: absolute;
    bottom: 0;
    right: 0;
    width: 24rpx;
    height: 24rpx;
    border-radius: $radius-full;
    border: 3rpx solid $bg-elevated;
    background: $text-disabled;
    
    &.status-online {
      background: $success-color;
      box-shadow: 0 2rpx 8rpx rgba($success-color, 0.4);
    }
  }

  // 点击效果
  &:active {
    transform: scale(0.95);
  }
}
</style>