<template>
  <view class="segmented-control" :class="[`segment-${size}`]">
    <view
      v-for="(option, index) in options"
      :key="index"
      class="segment-item"
      :class="{ 'segment-active': modelValue === option.value }"
      @tap="handleSelect(option.value)"
    >
      <text class="segment-text">{{ option.label }}</text>
    </view>
    
    <!-- 滑动指示器 -->
    <view 
      class="segment-indicator"
      :style="indicatorStyle"
    ></view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Option {
  label: string
  value: string | number
}

interface Props {
  options: Option[]
  modelValue: string | number
  size?: 'sm' | 'md' | 'lg'
}

const props = withDefaults(defineProps<Props>(), {
  size: 'md'
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string | number): void
}>()

const activeIndex = computed(() => {
  return props.options.findIndex(opt => opt.value === props.modelValue)
})

const indicatorStyle = computed(() => {
  const index = activeIndex.value
  const width = `${100 / props.options.length}%`
  
  return {
    width,
    transform: `translateX(${index * 100}%)`
  }
})

function handleSelect(value: string | number) {
  if (value !== props.modelValue) {
    emit('update:modelValue', value)
  }
}
</script>

<style lang="scss" scoped>

.segmented-control {
  position: relative;
  display: flex;
  background: rgba(255, 255, 255, 0.08);
  border-radius: $radius-sm;
  padding: 4rpx;
  
  // 尺寸变体
  &.segment-sm {
    height: 64rpx;
    
    .segment-text {
      font-size: $font-size-body_sm;
    }
  }

  &.segment-md {
    height: 80rpx;
    
    .segment-text {
      font-size: $font-size-body;
    }
  }

  &.segment-lg {
    height: 96rpx;
    
    .segment-text {
      font-size: $font-size-body-lg;
    }
  }

  // 选项
  .segment-item {
    flex: 1;
    @include flex-center;
    position: relative;
    z-index: 2;
    cursor: pointer;
    transition: color $duration-fast $ease-standard;

    .segment-text {
      font-weight: $font-weight-medium;
      letter-spacing: $letter-spacing-wide;
      transition: color $duration-fast $ease-standard;
      color: $text-tertiary;
    }

    // 激活状态
    &.segment-active .segment-text {
      color: $text-primary;
      font-weight: $font-weight-semibold;
    }

    &:active {
      transform: scale(0.98);
    }
  }

  // 滑动指示器
  .segment-indicator {
    position: absolute;
    top: 4rpx;
    bottom: 4rpx;
    left: 4rpx;
    background: $primary-gradient;
    border-radius: calc(#{$radius-sm} - 2rpx);
    z-index: 1;
    transition: left $duration-normal $ease-spring,
              width $duration-normal $ease-spring;
    box-shadow: 0 2rpx 8rpx rgba(102, 126, 234, 0.3);
  }
}
</style>