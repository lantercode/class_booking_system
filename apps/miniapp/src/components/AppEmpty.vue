<template>
  <view class="app-empty" :class="[`empty-${variant}`]">
    <!-- 图标区域 -->
    <view class="empty-icon-wrapper">
      <view v-if="icon" class="empty-icon">
        <text>{{ icon }}</text>
      </view>
      <image 
        v-else-if="image" 
        :src="image" 
        mode="aspectFit"
        class="empty-image"
      />
    </view>

    <!-- 文字区域 -->
    <view class="empty-content">
      <text v-if="title" class="empty-title">{{ title }}</text>
      <text v-if="description" class="empty-description">{{ description }}</text>
    </view>

    <!-- 操作按钮 -->
    <view v-if="$slots.action || actionText" class="empty-action">
      <slot name="action">
        <AppButton 
          v-if="actionText" 
          :text="actionText" 
          variant="secondary"
          size="sm"
          @tap="$emit('action')"
        />
      </slot>
    </view>
  </view>
</template>

<script setup lang="ts">
import AppButton from './AppButton.vue'

interface Props {
  icon?: string
  image?: string
  title?: string
  description?: string
  actionText?: string
  variant?: 'default' | 'compact'
}

withDefaults(defineProps<Props>(), {
  icon: '📭',
  image: '',
  title: '',
  description: '',
  actionText: '',
  variant: 'default'
})

defineEmits<{
  (e: 'action'): void
}>()
</script>

<style lang="scss" scoped>

.app-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  
  // 图标区域
  .empty-icon-wrapper {
    margin-bottom: $space-lg;

    .empty-icon {
      @include flex-center;
      width: 160rpx;
      height: 160rpx;
      
      text {
        font-size: 120rpx;
        line-height: 1;
      }
    }

    .empty-image {
      width: 240rpx;
      height: 240rpx;
    }
  }

  // 内容区域
  .empty-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    margin-bottom: $space-lg;
    
    .empty-title {
      @include text-h4;
      color: inherit;
      margin-bottom: $vr-tight;
      text-align: center;
    }

    .empty-description {
      @include text-caption;
      color: inherit;
      opacity: 0.7;
      text-align: center;
      max-width: 480rpx;
    }
  }

  // 操作区域
  .empty-action {
    margin-top: $space-sm;
  }

  // ------------------------------------------
  // 变体：default（标准尺寸）
  // ------------------------------------------
  &.empty-default {
    padding: $space-3xl $space-md;

    .empty-icon-wrapper {
      margin-bottom: $space-xl;
    }

    .empty-content {
      margin-bottom: $space-xl;
    }
  }

  // ------------------------------------------
  // 变体：compact（紧凑型，用于列表内）
  // ------------------------------------------
  &.empty-compact {
    padding: $space-2xl $space-md;

    .empty-icon-wrapper {
      margin-bottom: $space-md;

      .empty-icon {
        width: 120rpx;
        height: 120rpx;

        text {
          font-size: 80rpx;
        }
      }

      .empty-image {
        width: 160rpx;
        height: 160rpx;
      }
    }

    .empty-content {
      margin-bottom: $space-md;
    }
  }
}
</style>