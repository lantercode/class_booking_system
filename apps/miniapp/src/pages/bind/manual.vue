<template>
  <view class="manual-bind-page">
    
    <!-- 背景装饰 -->
    <view class="bg-decoration">
      <view class="glow-circle glow-1"></view>
      <view class="glow-circle glow-2"></view>
    </view>

    <view class="page-container">
      
      <!-- 说明区域 - 玻璃态卡片 -->
      <view class="info-section glass-card">
        <view class="info-icon-wrapper">
          <text class="info-icon">📋</text>
          <view class="icon-glow-effect"></view>
        </view>
        
        <text class="info-title">添加机构登记的手机号</text>
        <text class="info-desc">
          您微信绑定的手机号与机构登记的不一致<br/>
          请在此输入机构登记的手机号完成绑定
        </text>
      </view>

      <!-- 表单区域 - 玻璃态卡片 -->
      <view class="form-section glass-card">
        
        <!-- 手机号输入 -->
        <view class="form-item">
          <view class="label-wrapper">
            <text class="form-label">📱 手机号码</text>
            <text v-if="formData.value" class="char-count">{{ formData.value.length }}/11</text>
          </view>
          
          <view class="phone-input-wrapper" :class="{ 'input-focused': isPhoneFocused }">
            <view class="prefix-box">
              <text class="phone-prefix">+86</text>
              <view class="prefix-divider"></view>
            </view>
            
            <input
              v-model="formData.value"
              type="number"
              maxlength="11"
              placeholder="请输入机构登记的手机号"
              class="phone-input"
              :disabled="isLoading"
              @focus="isPhoneFocused = true"
              @blur="isPhoneFocused = false"
            />
            
            <view v-if="formData.value && isFormValid" class="valid-icon">
              <text>✓</text>
            </view>
          </view>
          
          <view v-if="formData.value && !isFormValid" class="error-hint">
            <text class="error-text">⚠️ 请输入正确的11位手机号</text>
          </view>
        </view>

      </view>

      <!-- 提交按钮 -->
      <button 
        class="submit-btn"
        :class="{ 
          'btn-disabled': !isFormValid || isLoading, 
          'btn-loading': isLoading,
          'btn-valid': isFormValid && !isLoading
        }"
        :disabled="!isFormValid || isLoading"
        @tap="handleSubmit"
      >
        <view v-if="isLoading" class="loading-spinner"></view>
        <text v-else class="btn-text-content">{{ '确认绑定' }}</text>
      </button>

      <!-- 底部提示信息 -->
      <view class="bottom-tips">
        <view class="tips-icon-wrapper">
          <text class="tips-icon">💡</text>
        </view>
        <text class="tips-text">遇到问题？请联系机构管理员</text>
      </view>

    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { wechatBindPhoneManual } from '@/utils/wechat'
import { redirectToHome } from '@/utils/auth'

const bindToken = ref('')
const isLoading = ref(false)
const isPhoneFocused = ref(false)

const formData = ref({
  value: ''
})

onMounted(() => {
  const pages = getCurrentPages()
  const currentPage = pages[pages.length - 1]
  const options = (currentPage as any).options || {}
  
  bindToken.value = decodeURIComponent(options.bindToken || '')
  
  console.log('📝 手动输入页加载, bindToken:', bindToken.value ? '已获取' : '未获取')
})

const isFormValid = computed(() => {
  return /^1[3-9]\d{9}$/.test(formData.value.value)
})

async function handleSubmit() {
  if (!isFormValid.value || isLoading.value) return

  if (!bindToken.value) {
    uni.showToast({ title: '凭证已过期，请重新登录', icon: 'none' })
    return
  }

  isLoading.value = true

  try {
    uni.showLoading({ title: '绑定中...' })
    
    const result = await wechatBindPhoneManual(bindToken.value, formData.value.value)

    uni.hideLoading()

    if (result.success) {
      uni.showToast({
        title: '绑定成功！',
        icon: 'success',
        duration: 1500
      })

      setTimeout(() => {
        redirectToHome(result.role)
      }, 1500)
    } else {
      uni.showToast({
        title: result.msg || '未找到该手机号的学员信息',
        icon: 'none',
        duration: 2500
      })
    }

  } catch (error: any) {
    console.error('❌ 手动绑定失败:', error)
    uni.hideLoading()
    uni.showToast({
      title: error.message || '绑定失败，请重试',
      icon: 'none',
      duration: 2000
    })
  } finally {
    isLoading.value = false
  }
}
</script>

<style lang="scss">
// @use '@/styles/theme/variables' as *;

.manual-bind-page {
  min-height: 100vh;
  background: $gradient-page;
  position: relative;
  overflow-x: hidden;

  // 背景装饰光效
  .bg-decoration {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    pointer-events: none;
    overflow: hidden;
    
    .glow-circle {
      position: absolute;
      border-radius: 50%;
      filter: blur(80rpx);
      
      &.glow-1 {
        width: 400rpx;
        height: 400rpx;
        top: -100rpx;
        right: -100rpx;
        background: rgba(102, 126, 234, 0.15);
        animation: floatGlow 8s ease-in-out infinite;
      }
      
      &.glow-2 {
        width: 300rpx;
        height: 300rpx;
        bottom: 200rpx;
        left: -80rpx;
        background: rgba(118, 75, 162, 0.12);
        animation: floatGlow 10s ease-in-out infinite reverse;
      }
    }
  }

  // 玻璃态卡片通用样式
  .glass-card {
    background: $glass-bg-heavy;
    backdrop-filter: $glass-blur;
    -webkit-backdrop-filter: $glass-blur;
    border: $glass-border;
    box-shadow: $glass-shadow;
  }

  .page-container {
    position: relative;
    z-index: 1;
    padding: $space-xl $space-lg;
    padding-top: calc(env(safe-area-inset-top) + 120rpx);

    // 说明区域
    .info-section {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: $space-2xl $space-lg;
      margin-bottom: $space-lg;
      border-radius: $radius-2xl;
      text-align: center;

      .info-icon-wrapper {
        width: 120rpx;
        height: 120rpx;
        margin-bottom: $space-md;
        position: relative;
        display: flex;
        align-items: center;
        justify-content: center;

        .icon-glow-effect {
          position: absolute;
          width: 100%;
          height: 100%;
          background: radial-gradient(circle, rgba(102, 126, 234, 0.25), transparent);
          border-radius: 50%;
          animation: iconPulse 3s ease-in-out infinite;
        }

        .info-icon {
          font-size: 56rpx;
          position: relative;
          z-index: 1;
        }
      }

      .info-title {
        font-size: $font-size-h3;
        font-weight: $font-weight-semibold;
        color: $text-primary;
        margin-bottom: $space-sm;
        letter-spacing: $letter-spacing-tight;
      }

      .info-desc {
        font-size: $font-size-body_sm;
        color: $text-secondary;
        line-height: $line-height-relaxed;
        max-width: 520rpx;
      }
    }

    // 表单区域
    .form-section {
      border-radius: $radius-2xl;
      padding: $space-lg;
      margin-bottom: $space-xl;

      .form-item {
        display: flex;
        flex-direction: column;
        gap: $space-xs;

        .label-wrapper {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: $space-xs;

          .form-label {
            font-size: $font-size-body_lg;
            font-weight: $font-weight-medium;
            color: $text-primary;
          }

          .char-count {
            font-size: $font-size-caption;
            color: $text-tertiary;
          }
        }

        .phone-input-wrapper {
          display: flex;
          align-items: center;
          background: rgba(255, 255, 255, 0.05);
          border: 2rpx solid $border-light;
          border-radius: $radius-lg;
          padding: 0 $space-md;
          transition: all $duration-fast $ease-standard;

          &.input-focused {
            border-color: $primary-solid;
            background: rgba(102, 126, 234, 0.08);
            box-shadow: 0 0 20rpx rgba(102, 126, 234, 0.15);
          }

          .prefix-box {
            display: flex;
            align-items: center;
            gap: $space-xs;
            padding-right: $space-sm;
            margin-right: $space-sm;

            .phone-prefix {
              font-size: $font-size-body;
              font-weight: $font-weight-semibold;
              color: $text-secondary;
            }

            .prefix-divider {
              width: 2rpx;
              height: 36rpx;
              background: $border-light;
            }
          }

          .phone-input {
            flex: 1;
            height: $input-height-sm;
            font-size: $font-size-body;
            color: $text-primary;
            
            &::placeholder {
              color: $text-disabled;
            }
          }

          .valid-icon {
            width: 44rpx;
            height: 44rpx;
            background: rgba(82, 196, 26, 0.15);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;

            text {
              color: $success-color;
              font-size: $font-size-body_lg;
              font-weight: $font-weight-bold;
            }
          }
        }

        .error-hint {
          margin-top: $space-xs;
          
          .error-text {
            font-size: $font-size-caption;
            color: $error-color;
          }
        }
      }
    }

    // 提交按钮
    .submit-btn {
      width: 100%;
      height: $button-height-lg;
      line-height: $button-height-lg;
      background: $primary-gradient;         // 更新：使用香槟金渐变（替代微信绿）
      color: #fff;
      font-size: $font-size-h4;
      font-weight: $font-weight-semibold;
      border-radius: $radius-2xl;
      border: none;
      margin-bottom: $space-xl;
      box-shadow: $shadow-button;            // 香槟金阴影（替代微信绿）
      transition: all $duration-fast $ease-standard;
      display: flex;
      align-items: center;
      justify-content: center;

      &::after {
        display: none !important;
      }

      &.btn-valid {
        &:active {
          transform: scale(0.98) translateY(2rpx);
          box-shadow: $shadow-sm;           // 更新：使用柔和阴影（替代绿色）
        }
      }

      &.btn-loading {
        opacity: 0.88;
        
        .loading-spinner {
          width: 40rpx;
          height: 40rpx;
          border: 4rpx solid rgba(255, 255, 255, 0.3);
          border-top-color: #fff;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }
      }

      &.btn-disabled {
        background: $bg-elevated;                    // 使用提升背景色（可见的按钮底色）
        color: $text-disabled;
        border: 2rpx solid $border-subtle;           // 添加浅边框，明确按钮边界
        box-shadow: $shadow-inner;                   // 使用内阴影（凹陷效果）
        cursor: not-allowed;
        opacity: 0.75;                               // 适度降低透明度（保留可见性）
      }

      .btn-text-content {
        letter-spacing: $letter-spacing-wide;
      }
    }

    // 底部提示
    .bottom-tips {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: $space-xs;
      padding-top: $space-lg;

      .tips-icon-wrapper {
        .tips-icon {
          font-size: 28rpx;
        }
      }

      .tips-text {
        font-size: $font-size-caption;
        color: $text-tertiary;
      }
    }

    // 品牌Slogan区域
    .brand-slogan-section {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding-top: $space-xl;
      padding-bottom: $space-2xl;

      .brand-slogan-text {
        font-size: $font-size-body-sm;
        font-weight: $font-weight-medium;
        color: $primary-solid;                    // 使用香槟金色
        letter-spacing: $letter-spacing-wider;     // 加宽字间距，优雅感
        opacity: 0.85;                            // 适度透明度，不抢焦点
        background: linear-gradient(
          135deg,
          $primary-solid 0%,
          $accent-light 100%
        );
        -webkit-background-clip: text;            // iOS Safari 兼容
        -webkit-text-fill-color: transparent;     // 渐变文字效果
        background-clip: text;
        transition: all $duration-slow $ease-out;

        &:active {
          opacity: 1;
          transform: scale(1.02);
        }
      }

      .slogan-divider {
        width: 120rpx;
        height: 2rpx;
        margin-top: $space-md;
        background: linear-gradient(
          90deg,
          transparent 0%,
          rgba(201, 166, 107, 0.3) 50%,
          transparent 100%
        );                                        // 香槟金色渐变分割线
        border-radius: $radius-full;
      }
    }
  }
}

// 动画关键帧
@keyframes floatGlow {
  0%, 100% { 
    transform: translate(0, 0) scale(1); 
  }
  33% { 
    transform: translate(30rpx, -30rpx) scale(1.05); 
  }
  66% { 
    transform: translate(-20rpx, 20rpx) scale(0.95); 
  }
}

@keyframes iconPulse {
  0%, 100% { 
    transform: scale(1); 
    opacity: 0.5; 
  }
  50% { 
    transform: scale(1.1); 
    opacity: 0.7; 
  }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>