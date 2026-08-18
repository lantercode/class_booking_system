<template>
  <view class="app-input" :class="[`input-${variant}`, { 'input-focused': isFocused, 'input-error': error }]">
    <!-- 左侧图标 -->
    <view v-if="$slots.prefix || icon" class="input-prefix">
      <slot name="prefix">
        <text class="input-icon">{{ icon }}</text>
      </slot>
    </view>

    <!-- 输入框 -->
    <input
      ref="inputRef"
      :type="type"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      :maxlength="maxlength"
      :password="type === 'password'"
      class="input-field"
      @input="handleInput"
      @focus="handleFocus"
      @blur="handleBlur"
      @confirm="handleConfirm"
    />

    <!-- 右侧操作区 -->
    <view v-if="$slots.suffix || clearable || showPasswordToggle" class="input-suffix">
      <!-- 清除按钮 -->
      <view 
        v-if="clearable && modelValue && !disabled" 
        class="input-clear"
        @tap.stop="handleClear"
      >
        <text>✕</text>
      </view>

      <!-- 密码显示切换 -->
      <view 
        v-if="showPasswordToggle && type === 'password' && modelValue" 
        class="input-toggle"
        @tap.stop="togglePasswordVisibility"
      >
        <text>{{ showPassword ? '🙈' : '👁️' }}</text>
      </view>

      <!-- 自定义后缀插槽 -->
      <slot name="suffix"></slot>
    </view>

    <!-- 错误提示 -->
    <view v-if="error" class="input-error">
      <text>{{ error }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface Props {
  modelValue?: string | number
  type?: 'text' | 'number' | 'password' | 'digit'
  placeholder?: string
  icon?: string
  disabled?: boolean
  clearable?: boolean
  showPasswordToggle?: boolean
  maxlength?: number
  error?: string
  variant?: 'default' | 'filled' | 'outlined'
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: '',
  type: 'text',
  placeholder: '',
  icon: '',
  disabled: false,
  clearable: false,
  showPasswordToggle: false,
  maxlength: -1,
  error: '',
  variant: 'default'
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'focus', event: Event): void
  (e: 'blur', event: Event): void
  (e: 'confirm', value: string): void
}>()

const isFocused = ref(false)
const showPassword = ref(false)

function handleInput(e: any) {
  emit('update:modelValue', e.detail.value)
}

function handleFocus(e: any) {
  isFocused.value = true
  emit('focus', e)
}

function handleBlur(e: any) {
  isFocused.value = false
  emit('blur', e)
}

function handleConfirm(e: any) {
  emit('confirm', e.detail.value)
}

function handleClear() {
  emit('update:modelValue', '')
}

function togglePasswordVisibility() {
  showPassword.value = !showPassword.value
}
</script>

<style lang="scss" scoped>

.app-input {
  position: relative;
  display: flex;
  align-items: center;
  
  // 图标区域
  .input-prefix,
  .input-suffix {
    @include flex-center;
    flex-shrink: 0;
  }

  .input-prefix {
    margin-right: $space-xs;
  }

  .input-suffix {
    margin-left: $space-xs;
    gap: $space-2xs;
  }

  .input-icon {
    font-size: $icon-size-md;
    color: $text-tertiary;
    transition: color $duration-fast $ease-standard;
  }

  // 清除/切换按钮
  .input-clear,
  .input-toggle {
    width: 44rpx;
    height: 44rpx;
    border-radius: $radius-full;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.1);
    
    text {
      font-size: $font-size-caption;
      color: $text-secondary;
    }

    &:active {
      background: rgba(255, 255, 255, 0.2);
    }
  }

  // 输入框
  .input-field {
    flex: 1;
    height: $input-height;
    padding: 0 $space-sm;
    font-size: $font-size-body;
    color: inherit;
    background: transparent;

    &::placeholder {
      color: $text-tertiary;
    }
  }

  // 错误提示
  .input-error {
    position: absolute;
    bottom: -32rpx;
    left: 0;
    
    text {
      @include text-caption;
      color: $error-color;
    }
  }

  // ------------------------------------------
  // 变体：default（深色背景页）
  // ------------------------------------------
  &.input-default {
    height: $input-height;
    padding: 0 $space-md;
    background: $glass-bg;
    border: 2rpx solid transparent;
    border-radius: $radius-sm;
    color: $text-primary;
    transition: box-shadow $duration-fast $ease-standard,
              background $duration-fast $ease-standard;

    &:hover,
    &.input-focused {
      border-color: $primary-border;
      box-shadow: $glow-primary;
      
      .input-icon {
        color: $primary-light;
      }
    }

    &.input-error {
      border-color: rgba($error-color, 0.5);
      box-shadow: 0 0 20rpx rgba($error-color, 0.15);
    }

    &.input-disabled {
      opacity: 0.5;
      pointer-events: none;
    }
  }

  // ------------------------------------------
  // 变体：filled（填充式，浅色背景）
  // ------------------------------------------
  &.input-filled {
    height: $input-height;
    padding: 0 $space-md;
    background: $bg-tertiary;
    border: none;
    border-radius: $radius-sm;
    color: $text-primary;
    transition: border-color $duration-fast $ease-standard,
              box-shadow $duration-fast $ease-standard,
              background $duration-fast $ease-standard;

    &:hover,
    &.input-focused {
      background: $bg-elevated;
      box-shadow: $glow-primary;         // ✅ 更新：使用香槟金光晕（替代紫色）
    }

    .input-icon {
      color: $text-tertiary;
    }

    &.input-focused .input-icon {
      color: $primary-solid;
    }

    &.input-error {
      background: tint($error-color, 95%);
    }
  }

  // ------------------------------------------
  // 变体：outlined（描边式）
  // ------------------------------------------
  &.input-outlined {
    height: $input-height;
    padding: 0 $space-md;
    background: transparent;
    border: 3rpx solid rgba(26, 26, 26, 0.40);     // ✅ 再次大幅加深边框（28%→40%，+43%）并加粗（2.5rpx→3rpx），确保清晰可见
    border-radius: $radius-sm;
    color: $text-primary;
    box-shadow: inset 0 2rpx 6rpx rgba(0, 0, 0, 0.10);  // ✅ 显著增强内阴影（更深更广，强烈立体感）

    transition: border-color $duration-fast $ease-standard,
              box-shadow $duration-fast $ease-standard,
              background $duration-fast $ease-standard;

    &:hover,
    &.input-focused {
      border-color: $primary-solid;
      box-shadow: inset 0 2rpx 6rpx rgba(0, 0, 0, 0.10),
                  0 0 0 4rpx rgba(201, 166, 107, 0.15);
    }

    .input-icon {
      color: $text-tertiary;
    }

    &.input-focused .input-icon {
      color: $primary-solid;
    }

    &.input-error {
      border-color: $error-color;
    }
  }
}
</style>