<template>
  <view class="app-loading" :class="[`loading-${type}`, { 'loading-fullscreen': fullscreen }]">
    <!-- Spinner 类型 -->
    <template v-if="type === 'spinner'">
      <view class="spinner-wrapper">
        <view class="spinner" :style="{ borderColor: color }"></view>
        <text v-if="text" class="loading-text">{{ text }}</text>
      </view>
    </template>

    <!-- Skeleton 骨架屏类型 -->
    <template v-else-if="type === 'skeleton'">
      <view class="skeleton-container">
        <slot></slot>
        
        <!-- 默认骨架结构 -->
        <view v-if="!$slots.default" class="skeleton-default">
          <view class="skeleton-avatar"></view>
          <view class="skeleton-content">
            <view class="skeleton-title"></view>
            <view class="skeleton-text"></view>
            <view class="skeleton-text short"></view>
          </view>
        </view>
      </view>
    </template>

    <!-- Progress 进度条类型 -->
    <template v-else-if="type === 'progress'">
      <view class="progress-wrapper">
        <view class="progress-bar">
          <view 
            class="progress-fill"
            :style="{ width: `${percent}%`, background: color }"
          ></view>
        </view>
        <text v-if="showPercent" class="progress-text">{{ percent }}%</text>
      </view>
    </template>

    <!-- Dots 点状加载 -->
    <template v-else-if="type === 'dots'">
      <view class="dots-wrapper">
        <view 
          v-for="(dot, index) in 3" 
          :key="index"
          class="dot"
          :style="{ 
            animationDelay: `${index * 0.15}s`,
            background: color 
          }"
        ></view>
        <text v-if="text" class="loading-text">{{ text }}</text>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
interface Props {
  type?: 'spinner' | 'skeleton' | 'progress' | 'dots'
  text?: string
  color?: string
  percent?: number
  showPercent?: boolean
  fullscreen?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  type: 'spinner',
  text: '',
  color: '#667eea',
  percent: 0,
  showPercent: false,
  fullscreen: false
})
</script>

<style lang="scss" scoped>

.app-loading {
  display: flex;
  align-items: center;
  justify-content: center;

  // 全屏模式
  &.loading-fullscreen {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: $bg-overlay;           // 更新：使用新的遮罩层变量（米白主题下的半透明黑）
    backdrop-filter: blur(10rpx);
    z-index: $z-modal;
  }

  // 加载文字
  .loading-text {
    @include text-caption;
    margin-top: $space-sm;
    opacity: 0.7;
  }

  // ------------------------------------------
  // Spinner（旋转器）
  // ------------------------------------------
  .spinner-wrapper {
    @include flex-column;
    align-items: center;
    gap: $vr-normal;
  }

  .spinner {
    width: 64rpx;
    height: 64rpx;
    border: 4rpx solid transparent;
    border-top-color: currentColor;
    border-radius: $radius-full;
    animation: spin 0.8s linear infinite;
  }

  // ------------------------------------------
  // Skeleton（骨架屏）
  // ------------------------------------------
  .skeleton-container {
    width: 100%;
    padding: $space-md;
  }

  .skeleton-default {
    @include flex-row-center;
    gap: $space-md;

    .skeleton-avatar {
      width: 96rpx;
      height: 96rpx;
      border-radius: $radius-full;
      @include shimmer;
    }

    .skeleton-content {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: $vr-relaxed;

      .skeleton-title {
        height: 36rpx;
        width: 60%;
        border-radius: $radius-xs;
        @include shimmer;
      }

      .skeleton-text {
        height: 28rpx;
        width: 100%;
        border-radius: $radius-xs;
        @include shimmer;

        &.short {
          width: 40%;
        }
      }
    }
  }

  // 自定义骨架块
  :deep(.skeleton-block) {
    border-radius: $radius-xs;
    @include shimmer;
  }

  // ------------------------------------------
  // Progress（进度条）
  // ------------------------------------------
  .progress-wrapper {
    width: 100%;
    max-width: 400rpx;
    @include flex-column;
    gap: $vr-tight;
  }

  .progress-bar {
    width: 100%;
    height: 8rpx;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 4rpx;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    border-radius: 4rpx;
    transition: width $duration-slow $ease-standard;
    animation: progressFill 2s ease-in-out infinite alternate;
  }

  .progress-text {
    @include text-caption;
    text-align: center;
  }

  // ------------------------------------------
  // Dots（点状动画）
  // ------------------------------------------
  .dots-wrapper {
    @include flex-column;
    align-items: center;
    gap: $vr-normal;
  }

  .dot {
    width: 16rpx;
    height: 16rpx;
    border-radius: $radius-full;
    animation: dotPulse 1.4s ease-in-out infinite both;
  }
}
</style>