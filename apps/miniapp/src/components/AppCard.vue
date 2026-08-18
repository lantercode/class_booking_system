<template>
  <view
    class="app-card"
    :class="[
      `card-${variant}`,
      { 
        'card-clickable': clickable,
        'card-active': isActive,
        'card-disabled': disabled
      }
    ]"
    :style="customStyle"
    @tap="handleTap"
  >
    <!-- 卡片内容 -->
    <view class="card-inner">
      <!-- 装饰条（可选） -->
      <view v-if="showAccent" class="card-accent" :style="{ background: accentColor }"></view>
      
      <!-- 头部插槽 -->
      <view v-if="$slots.header || title" class="card-header">
        <slot name="header">
          <text v-if="title" class="card-title">{{ title }}</text>
        </slot>
        <slot name="header-extra"></slot>
      </view>

      <!-- 默认内容插槽 -->
      <view class="card-body" :class="{ 'card-body-no-padding': noPadding }">
        <slot></slot>
      </view>

      <!-- 底部插槽 -->
      <view v-if="$slots.footer" class="card-footer">
        <slot name="footer"></slot>
      </view>
    </view>

    <!-- 光泽效果（点击时） -->
    <view v-if="clickable" class="card-shine"></view>
    
    <!-- 发光效果（激活状态） -->
    <view v-if="isActive && glowColor" class="card-glow" :style="{ background: glowColor }"></view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  variant?: 'default' | 'glass' | 'elevated' | 'data'
  padding?: 'sm' | 'md' | 'lg' | 'none'
  clickable?: boolean
  disabled?: boolean
  active?: boolean
  title?: string
  showAccent?: boolean
  accentColor?: string
  glowColor?: string
  customStyle?: string
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'default',
  padding: 'md',
  clickable: false,
  disabled: false,
  active: false,
  showAccent: false,
  accentColor: '',
  glowColor: ''
})

const emit = defineEmits<{
  (e: 'tap'): void
}>()

const isActive = computed(() => props.active)
const noPadding = computed(() => props.padding === 'none')

function handleTap() {
  if (props.clickable && !props.disabled) {
    emit('tap')
  }
}
</script>

<style lang="scss" scoped>

.app-card {
  position: relative;
  border-radius: $radius-md;
  overflow: hidden;
  transition: transform $duration-normal $ease-standard,
            box-shadow $duration-normal $ease-standard,
            opacity $duration-normal $ease-standard;

  .card-inner {
    position: relative;
    z-index: 1;
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  // 内边距变体
  &.card-sm > .card-inner {
    padding: $card-padding-sm;
  }

  &.card-md > .card-inner,
  &:not([class*='card-']) > .card-inner {
    padding: $card-padding-md;
  }

  &.card-lg > .card-inner {
    padding: $card-padding-lg;
  }

  // 无内边距
  .card-body-no-padding {
    padding: 0 !important;
  }

  // 装饰条
  .card-accent {
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 6rpx;
    border-radius: 0 3rpx 3rpx 0;
  }

  // 头部区域
  .card-header {
    @include flex-between;
    margin-bottom: $space-sm;

    .card-title {
      @include text-h3;
      color: inherit;
    }
  }

  // 内容区域
  .card-body {
    flex: 1;
  }

  // 底部区域
  .card-footer {
    margin-top: $space-md;
    padding-top: $space-sm;
    border-top: 1rpx solid $border-subtle;
  }

  // 光泽效果
  .card-shine {
    position: absolute;
    top: 0;
    left: -100%;
    width: 50%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.12), transparent);
    transform: skewX(-20deg);
    transition: left $duration-slow $ease-standard;
    pointer-events: none;
  }

  // 发光效果
  .card-glow {
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    opacity: 0;
    transition: opacity $duration-normal $ease-standard;
    background: radial-gradient(circle, rgba(102, 126, 234, 0.25) 0%, transparent 70%);
    pointer-events: none;
  }

  // ------------------------------------------
  // 变体：default（白色背景，用于浅色主题页）
  // ------------------------------------------
  &.card-default {
    background: $bg-elevated;
    @include elevation(2);

    .card-title {
      color: $text-primary;
    }
  }

  // ------------------------------------------
  // 变体：glass（毛玻璃效果，用于深色/渐变背景）
  // ------------------------------------------
  &.card-glass {
    @include glass-effect;
    color: $text-primary;

    .card-title {
      color: $text-primary;
    }

    .card-footer {
      border-top-color: $border-light;
    }
  }

  // ------------------------------------------
  // 变体：elevated（明显悬浮效果）
  // ------------------------------------------
  &.card-elevated {
    background: $bg-elevated;
    @include elevation(4);

    .card-title {
      color: $text-primary;
    }
  }

  // ------------------------------------------
  // 变体：data（数据展示卡片）
  // ------------------------------------------
  &.card-data {
    background: linear-gradient(
      135deg,
      rgba(102, 126, 234, 0.08) 0%,
      rgba(118, 75, 162, 0.04) 100%
    );
    border: 1rpx solid $primary-border;

    .card-title {
      color: $primary-solid;
    }
  }

  // ------------------------------------------
  // 交互状态
  // ------------------------------------------
  &.card-clickable {
    cursor: pointer;

    &:active {
      transform: scale(0.98);

      .card-shine {
        left: 150%;
      }
    }
  }

  &.card-active {
    border-color: $primary-border;
    // box-shadow: $glow-primary;

    .card-glow {
      opacity: 1;
    }
  }

  &.card-disabled {
    opacity: 0.5;
    pointer-events: none;
  }
}
</style>