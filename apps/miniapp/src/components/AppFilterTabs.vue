<template>
  <!-- 筛选标签组件 - 横向滚动，统一UI风格 -->
    <scroll-view scroll-x class="filter-scroll" :show-scrollbar="false">
    <view class="filter-list">
      <view
        v-for="tab in tabs"
        :key="tab.value"
        class="filter-pill"
        :class="{ 'pill-active': modelValue === tab.value }"
        @tap="handleTabClick(tab.value)"
      >
        <text>{{ tab.label }}</text>
      </view>
    </view>
  </scroll-view>
</template>

<script setup lang="ts">
interface TabItem {
  label: string
  value: string | number
}

interface Props {
  tabs: TabItem[]
  modelValue: string | number
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string | number): void
  (e: 'change', value: string | number): void
}>()

function handleTabClick(value: string | number) {
  if (props.modelValue !== value) {
    emit('update:modelValue', value)
    emit('change', value)
  }
}
</script>

<style lang="scss" scoped>

// 筛选标签滚动容器 - 统一背景色设计
.filter-scroll {
  white-space: nowrap;
  margin-bottom: $space-md;
  padding: 0 $space-md;
  border-radius: $radius-lg;
  background: rgba(255, 255, 255, 0.85);
  @include hide-scrollbar;
}

.filter-list {
  display: inline-flex;
  gap: $space-xs;
}

// 筛选 Pill 按钮 - 大幅提升可见性 + 修复边框遮挡
.filter-pill {
  @include badge-base(20rpx 32rpx, $radius-full, $font-size-body_sm);
  background: rgba(255, 255, 255, 0.85);
  border: 2rpx solid rgba(255, 255, 255, 0.28);
  color: $text-secondary;
  box-shadow: 0 2rpx 6rpx rgba(0, 0, 0, 0.08);
  box-sizing: border-box;
  line-height: 1.2;
  transition: background $duration-fast $ease-standard,
              color $duration-fast $ease-standard,
              border-color $duration-fast $ease-standard,
              box-shadow $duration-fast $ease-standard,
              transform $duration-fast $ease-standard;
  margin: 24rpx 0;

  &:active {
    transform: scale(0.96);
  }

  &.pill-active {
    background: $primary-gradient;
    color: $text-primary;
    border-color: transparent;
    box-shadow: 0 4rpx 16rpx rgba(102, 126, 234, 0.3);
  }
}
</style>