<template>
  <view 
    class="app-badge" 
    :class="[`badge-${variant}`, `badge-${size}`, { 'badge-dot': dot }]"
    :style="customStyle"
  >
    <!-- Dot 模式 -->
    <template v-if="dot">
      <view class="badge-dot-inner" :style="{ background: dotColor || badgeColor }"></view>
    </template>

    <!-- 正常模式 -->
    <template v-else>
      <text v-if="text" class="badge-text">{{ text }}</text>
      <slot></slot>
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  text?: string | number
  variant?: 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info' | 'default'
  size?: 'sm' | 'md' | 'lg'
  dot?: boolean
  dotColor?: string
  customStyle?: string
}

const props = withDefaults(defineProps<Props>(), {
  text: '',
  variant: 'default',
  size: 'md',
  dot: false,
  dotColor: '',
  customStyle: ''
})

const badgeColor = computed(() => {
  const colorMap = {
    primary: 'var(--badge-primary)',
    secondary: 'var(--badge-secondary)',
    success: 'var(--badge-success)',
    warning: 'var(--badge-warning)',
    error: 'var(--badge-error)',
    info: 'var(--badge-info)',
    default: 'var(--badge-default)'
  }
  return colorMap[props.variant] || colorMap.default
})
</script>

<style lang="scss" scoped>

.app-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;

  // ------------------------------------------
  // 尺寸变体
  // ------------------------------------------
  &.badge-sm {
    @include badge-base(4rpx 12rpx, $radius-full, $font-size-tiny);
    
    .badge-text {
      font-size: $font-size-tiny;
    }
  }

  &.badge-md {
    @include badge-base(6rpx 16rpx, $radius-full, $font-size-overline);
  }

  &.badge-lg {
    padding: 8rpx 20rpx;
    border-radius: $radius-full;
    font-size: $font-size-caption;
    font-weight: $font-weight-medium;
  }

  // ------------------------------------------
  // 颜色变体
  // ------------------------------------------
  &.badge-primary {
    background: rgba($primary-solid, 0.12);
    color: $primary-solid;
  }

  &.badge-secondary {
    background: rgba($accent-solid, 0.12);
    color: $accent-solid;
  }

  &.badge-success {
    background: $success-bg;
    color: $success-color;
  }

  &.badge-warning {
    background: $warning-bg;
    color: $warning-color;
  }

  &.badge-error {
    background: $error-bg;
    color: $error-color;
  }

  &.badge-info {
    background: $info-bg;
    color: $info-color;
  }

  &.badge-default {
    background: rgba($text-tertiary, 0.1);
    color: $text-secondary;
  }

  // ------------------------------------------
  // Dot 模式（小圆点）
  // ------------------------------------------
  &.badge-dot {
    width: 16rpx;
    height: 16rpx;
    padding: 0;
    position: relative;

    .badge-dot-inner {
      width: 100%;
      height: 100%;
      border-radius: $radius-full;
      animation: pulseSoft 2s ease-in-out infinite;
    }
  }
}
</style>