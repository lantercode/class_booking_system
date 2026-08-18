<template>
  <view
    class="app-navbar"
    :class="[`navbar-${variant}`, { 'navbar-transparent': transparent }]"
    :style="[customStyle, navbarStyle]"
  >
    <!-- 左侧区域 -->
    <view class="navbar-left" @tap="handleBack">
      <view v-if="showBack" class="back-button">
        <text class="back-icon">←</text>
      </view>
      <slot name="left" class="navbar-text"></slot>
    </view>

    <!-- 中央标题 -->
    <view class="navbar-center">
      <text v-if="title" class="navbar-title">{{ title }}</text>
      <slot name="center"></slot>
    </view>

    <!-- 右侧区域 -->
    <view class="navbar-right" :style="{ paddingRight: menuButtonRight + 'px' }">
      <slot name="right"></slot>
      <view v-if="!$slots.right && showPlaceholder" class="placeholder"></view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

interface Props {
  title?: string
  showBack?: boolean
  showPlaceholder?: boolean
  transparent?: boolean
  variant?: 'default' | 'light' | 'dark'
  customStyle?: string
}

const props = withDefaults(defineProps<Props>(), {
  title: '',
  showBack: true,
  showPlaceholder: true,
  transparent: false,
  variant: 'dark',
  customStyle: ''
})

const emit = defineEmits<{
  (e: 'back'): void
}>()

// 胶囊按钮位置信息
const systemInfo = uni.getSystemInfoSync()
const menuButton = uni.getMenuButtonBoundingClientRect()

const menuButtonTop = ref(menuButton.top || 0)
const menuButtonHeight = ref(menuButton.height || 32)
const menuButtonRight = ref(systemInfo.screenWidth - menuButton.right || 10)
const statusBarHeight = ref(systemInfo.statusBarHeight || 0)

// 计算导航栏动态样式
const navbarStyle = computed(() => {
  const paddingTop = statusBarHeight.value
  const navBarHeight = Math.max(menuButtonHeight.value + 10, 44) // 胶囊高度+间距，最小44px

  return {
    paddingTop: `${paddingTop}px`,
    height: `${paddingTop + navBarHeight}px`
  }
})

onMounted(() => {
  console.log('[AppNavbar] navbarStyle:', navbarStyle.value)
})

function handleBack() {
  if (props.showBack) {
    emit('back')
    uni.navigateBack({
      fail: () => {
        // ✅ 修复：项目未配置原生tabBar，不能使用switchTab
        // 使用reLaunch关闭所有页面并打开首页（避免页面栈堆积）
        uni.reLaunch({ url: '/pages/index/index' })
      }
    })
  }
}
</script>

<style lang="scss" scoped>
.app-navbar {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-left: $space-md;
  box-sizing: border-box;
  z-index: $z-sticky;
  transition: background $duration-normal $ease-standard,
              box-shadow $duration-normal $ease-standard,
              color $duration-normal $ease-standard;

  // 左侧区域 - 动态适配
  .navbar-left {
    min-width: 100rpx;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    height: 100%;  // 填满导航栏高度（不含状态栏）
    .navbar-text {
      font-size: 34rpx;
      font-weight: $font-weight-medium;
      color: $text-primary;
      line-height: 1.4;
    }
  }

  // 右侧区域 - 避免与胶囊按钮重叠
  .navbar-right {
    min-width: 100rpx;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    height: 100%;  // 填满导航栏高度
  }

  // 中央标题区 - 自适应宽度
  .navbar-center {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    height: 100%;  // 填满导航栏高度
  }

  // 返回按钮 - 尺寸与胶囊按钮协调
  .back-button {
    @include flex-center;
    width: 60rpx;
    height: 60rpx;  // 稍小于胶囊按钮
    border-radius: $radius-full;
    background: rgba(255, 255, 255, 0.1);
    transition: background $duration-fast $ease-standard,
                transform $duration-fast $ease-standard;

    &:active {
      transform: scale(0.92);
      background: rgba(255, 255, 255, 0.2);
    }
  }

  .back-icon {
    font-size: 34rpx;
    color: inherit;
  }

  // 占位元素 - 与胶囊按钮尺寸匹配
  .placeholder {
    width: 60rpx;   // 接近胶囊按钮宽度
    height: 60rpx;  // 接近胶囊按钮高度
  }

  // 标题样式
  .navbar-title {
    @include text-h3;
    color: inherit;
    @include text-truncate;
    max-width: 100%;
  }

  // ------------------------------------------
  // 变体：深色（默认，用于深色背景页面）
  // ------------------------------------------
  &.navbar-dark {
    color: $text-primary;

    &.navbar-transparent {
      background: transparent;
    }

    &:not(.navbar-transparent) {
      @include glass-effect;
    }

    .back-button {
      background: rgba(255, 255, 255, 0.1);

      .back-icon {
        color: $text-primary;
      }
    }
  }

  // ------------------------------------------
  // 变体：浅色（用于浅色背景页面）
  // ------------------------------------------
  &.navbar-light {
    color: $text-primary;                   // ✅ 修正
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur($glass-blur);
    box-shadow: $shadow-xs;

    .back-button {
      background: $bg-secondary;           // ✅ 修正

      .back-icon {
        color: $text-secondary;            // ✅ 修正
      }

      &:active {
        background: $bg-tertiary;          // ✅ 修正：替代 darken()
      }
    }
  }

  // ------------------------------------------
  // 变体：默认（纯白背景）
  // ------------------------------------------
  &.navbar-default {
    color: $text-primary;
    background: #ffffff;                   // ✅ 修正：使用纯白色
    border-bottom: 1rpx solid $border-light;

    .back-button {
      background: transparent;

      .back-icon {
        color: $text-primary;              // ✅ 修正
      }

      &:active {
        background: $bg-secondary;         // ✅ 修正
      }
    }
  }
}
</style>