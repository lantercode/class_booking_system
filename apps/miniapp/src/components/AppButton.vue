<template>
  <button
    class="app-button"
    :class="[
      `btn-${variant}`,
      `btn-${size}`,
      {
        'btn-block': block,
        'btn-loading': loading,
        'btn-disabled': disabled || loading
      }
    ]"
    :disabled="disabled || loading"
    :style="customStyle"
    @tap="handleTap"
  >
    <!-- 加载指示器 -->
    <view v-if="loading" class="button-loading">
      <view class="loading-spinner"></view>
    </view>

    <!-- 左侧图标插槽 -->
    <view v-if="$slots.icon && !loading" class="button-icon-left">
      <slot name="icon"></slot>
    </view>

    <!-- 按钮文字 -->
    <text v-if="!$slots.default" class="button-text">{{ text }}</text>
    <slot v-else></slot>

    <!-- 右侧图标/箭头 -->
    <view v-if="showArrow && !loading" class="button-arrow">
      <text>→</text>
    </view>
  </button>
</template>

<script setup lang="ts">
interface Props {
  text?: string
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  block?: boolean
  loading?: boolean
  disabled?: boolean
  showArrow?: boolean
  customStyle?: string
}

const props = withDefaults(defineProps<Props>(), {
  text: '',
  variant: 'primary',
  size: 'md',
  block: false,
  loading: false,
  disabled: false,
  showArrow: false,
  customStyle: ''
})

const emit = defineEmits<{
  (e: 'tap'): void
}>()

function handleTap() {
  if (!props.disabled && !props.loading) {
    emit('tap')
  }
}
</script>

<style lang="scss" scoped>

.app-button {
  @include button-base;
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: $space-2xs;
  white-space: nowrap;

  // 尺寸变体
  &.btn-sm {
    height: $button-height-sm;
    padding: 0 $space-md;
    
    .button-text {
      font-size: $font-size-body_sm;
    }

    .button-icon-left,
    .button-arrow {
      font-size: $icon-size-sm;
    }
  }

  &.btn-md {
    height: $button-height-md;
    padding: 0 $space-lg;
    
    .button-text {
      font-size: $font-size-body;
    }

    .button-icon-left,
    .button-arrow {
      font-size: $icon-size-md;
    }
  }

  &.btn-lg {
    height: $button-height-lg;
    padding: 0 $space-xl;
    
    .button-text {
      font-size: $font-size-body-lg;
    }

    .button-icon-left,
    .button-arrow {
      font-size: $icon-size-lg;
    }
  }

  // 块级按钮
  &.btn-block {
    width: 100%;
    display: flex;
  }

  // ------------------------------------------
  // 变体：primary（主按钮 - 渐变色）
  // ------------------------------------------
  &.btn-primary {
    background: $primary-gradient;
    color: $text-primary;
    box-shadow: 0 4rpx 16rpx rgba(102, 126, 234, 0.3);

    &:active:not(.btn-disabled) {
      transform: scale(0.96);
      box-shadow: 0 2rpx 8rpx rgba(102, 126, 234, 0.2);
    }

    &.btn-disabled {
      opacity: 0.5;
      background: color.adjust($primary-solid, $lightness: -10%);
    }
  }

  // ------------------------------------------
  // 变体：secondary（次要按钮 - 描边）
  // ------------------------------------------
  &.btn-secondary {
    background: transparent;
    color: $text-primary;
    border: 2rpx solid $border-normal;

    &:active:not(.btn-disabled) {
      transform: scale(0.96);
      background: rgba(255, 255, 255, 0.08);
      border-color: $border-strong;
    }

    &.btn-disabled {
      opacity: 0.4;
      border-color: $border-subtle;
    }
  }

  // ------------------------------------------
  // 变体：ghost（幽灵按钮 - 仅文字）
  // ------------------------------------------
  &.btn-ghost {
    background: transparent;
    color: $accent-solid;

    &:active:not(.btn-disabled) {
      transform: scale(0.96);
      background: $accent-bg;              // ✅ 更新：使用强调色背景（莫兰迪粉 rgba(217, 167, 176, 0.1)）
    }

    &.btn-disabled {
      color: $text-disabled;
    }
  }

  // ------------------------------------------
  // 变体：danger（危险操作）
  // ------------------------------------------
  &.btn-danger {
    background: linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%);
    color: $text-primary;
    box-shadow: 0 4rpx 16rpx rgba(255, 77, 79, 0.3);

    &:active:not(.btn-disabled) {
      transform: scale(0.96);
      box-shadow: 0 2rpx 8rpx rgba(255, 77, 79, 0.2);
    }

    &.btn-disabled {
      opacity: 0.5;
    }
  }

  // ------------------------------------------
  // 内部元素样式
  // ------------------------------------------
  .button-text {
    @include text-body;
    font-weight: $font-weight-semibold;
    letter-spacing: $letter-spacing-wide;
  }

  .button-icon-left {
    @include flex-center;
  }

  .button-arrow {
    @include flex-center;
    transition: transform $duration-fast $ease-standard;
  }

  &:active:not(.btn-disabled) .button-arrow {
    transform: translateX(4rpx);
  }

  // 加载状态
  .button-loading {
    @include flex-center;
    margin-right: $space-xs;
  }

  .loading-spinner {
    width: 32rpx;
    height: 32rpx;
    border: 3rpx solid currentColor;
    border-top-color: transparent;
    border-radius: $radius-full;
    animation: spin 0.8s linear infinite;
  }

  &.btn-loading {
    pointer-events: none;
  }

  &.btn-disabled {
    cursor: not-allowed;
  }
}
</style>