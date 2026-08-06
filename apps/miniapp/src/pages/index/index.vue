<template>
  <view class="auth-container">
    <!-- 动态背景层 -->
    <view class="bg-layer">
      <view class="gradient-bg"></view>
      <view class="light-orb orb-1"></view>
      <view class="light-orb orb-2"></view>
      <view class="light-orb orb-3"></view>
      <view class="grid-overlay"></view>
    </view>

    <!-- 主内容区 -->
    <view class="main-content">
      <!-- 顶部品牌区域 -->
      <view class="brand-section">
        <view class="brand-logo">
          <view class="logo-glow"></view>
          <text class="logo-icon">✨</text>
        </view>
        <text class="brand-name">舞蹈约课</text>
        <text class="brand-slogan">以舞沐心，向内生长</text>
        <view class="brand-line"></view>
      </view>

      <!-- 授权卡片区域 -->
      <view class="auth-card-wrapper">
        <view 
          class="auth-card" 
          :class="{ 'card-loading': isLoading, 'card-error': hasError }"
        >
          <!-- 卡片光效 -->
          <view class="card-glow"></view>
          
          <!-- 用户头像/信息展示区 -->
          <view class="user-info-area">
            <view v-if="!isLoading && !hasError" class="avatar-placeholder">
              <text class="avatar-icon">👤</text>
              <view class="avatar-ring"></view>
            </view>
            
            <!-- 加载状态 -->
            <view v-if="isLoading" class="loading-state">
              <view class="loading-spinner"></view>
              <text class="loading-text">{{ loadingText }}</text>
            </view>
            
            <!-- 错误状态 -->
            <view v-if="hasError" class="error-state">
              <text class="error-icon">⚠️</text>
              <text class="error-text">{{ errorMessage }}</text>
            </view>
          </view>

          <!-- 核心操作按钮 -->
          <view class="action-buttons">
            <!-- 微信一键登录按钮 -->
            <button
              v-if="!isLoading"
              class="wechat-login-btn"
              :class="{ 'btn-disabled': isLoggingIn }"
              :disabled="isLoggingIn || hasError"
              @tap="handleWechatLogin"
            >
              <view class="btn-content">
                <text class="wechat-btn-icon">💬</text>
                <text class="wechat-btn-text">
                  {{ hasError ? '重新授权' : '微信一键登录' }}
                </text>
              </view>
              <view class="btn-shine"></view>
            </button>

            <!-- 加载中状态按钮 -->
            <button
              v-if="isLoading"
              class="loading-btn"
              disabled
            >
              <view class="btn-loading-content">
                <view class="mini-spinner"></view>
                <text>{{ loadingText }}</text>
              </view>
            </button>
          </view>

          <!-- 协议提示 -->
          <view class="agreement-hint">
            <view 
              class="checkbox-wrapper" 
              @tap="agreed = !agreed"
            >
              <view class="custom-checkbox" :class="{ checked: agreed }">
                <text v-if="agreed" class="check-mark">✓</text>
              </view>
            </view>
            <text class="agreement-text">
              登录即表示同意
              <text class="link" @tap.stop="showAgreement">《用户服务协议》</text>
              和
              <text class="link" @tap.stop="showPrivacy">《隐私政策》</text>
            </text>
          </view>
        </view>


      </view>

      <!-- 手机号绑定弹窗 - 重构版 -->
      <view v-if="showBindModal" class="bind-modal-overlay" @tap="closeBindModal">
        <view class="bind-modal-content" @tap.stop>
          
          <!-- 顶部拖拽指示器 -->
          <view class="drag-indicator"></view>

          <!-- 品牌视觉区域（视觉锚点）-->
          <view class="brand-visual-area">
            <view class="brand-logo-container">
              <view class="logo-glow-ring ring-1"></view>
              <view class="logo-glow-ring ring-2"></view>
              <text class="brand-logo-emoji">📱</text>
            </view>
            
            <!-- 渐变装饰线 -->
            <view class="decorative-line"></view>
          </view>

          <!-- 信息区域（标题 + 说明）-->
          <view class="info-section">
            <text class="main-title">绑定手机号码</text>
            <text class="sub-description">
              用于账号安全验证和课程服务通知
            </text>
          </view>

          <!-- 主操作区：微信一键授权 -->
          <view class="primary-action-zone">
            <button 
              class="wechat-auth-btn"
              :class="{ 'is-loading': isBinding }"
              :disabled="isBinding"
              open-type="getPhoneNumber"
              @getphonenumber="handleModalGetPhoneNumber"
            >
              <view v-if="!isBinding" class="btn-main-content">
                <view class="wechat-icon-box">
                  <text class="wechat-icon-symbol">💬</text>
                </view>
                <text class="auth-btn-label">微信手机号一键授权</text>
                <view class="btn-highlight-effect"></view>
              </view>
              
              <view v-else class="btn-loading-state">
                <view class="loading-spinner-mini"></view>
                <text class="loading-text">正在验证...</text>
              </view>
            </button>
          </view>

          <!-- 次级操作：分隔线 + 其他手机号入口 -->
          <view class="secondary-action-zone">
            <view class="light-divider">
              <view class="divider-segment"></view>
              <text class="divider-label">或</text>
              <view class="divider-segment"></view>
            </view>

            <view class="manual-bind-trigger" @tap="goToManualBind">
              <text class="trigger-label">使用其他手机号</text>
              <text class="trigger-arrow">›</text>
            </view>
          </view>

          <!-- 弱提示：小型内联提示 -->
          <view class="inline-hint">
            <text class="hint-icon">⚠️</text>
            <text class="hint-text">手机号不一致时可使用此方式</text>
          </view>

        </view>
      </view>

      <!-- 底部品牌信息 -->
      <view class="footer-info">
        <text class="footer-brand">以舞沐心，向内生长</text>
        <view class="version-info">
          <text class="version-text">v1.0.0</text>
        </view>
      </view>
    </view>

    <!-- 新用户引导弹窗（可选） -->
    <view v-if="showNewUserGuide" class="modal-overlay" @tap="closeNewUserGuide">
      <view class="modal-content" @tap.stop>
        <text class="modal-title">🎉 欢迎加入！</text>
        <text class="modal-desc">检测到您是新用户，请完善基本信息</text>
        
        <view class="form-item">
          <input 
            v-model="newUserInfo.nickname" 
            placeholder="您的称呼" 
            class="modal-input"
          />
        </view>

        <view class="modal-actions">
          <button class="modal-btn secondary" @tap="closeNewUserGuide">稍后填写</button>
          <button class="modal-btn primary" @tap="completeNewUserGuide">开始使用</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { wechatAutoLogin, wechatBindPhone } from '@/utils/wechat'
import { redirectToHome, validateToken } from '@/utils/auth'

const isLoading = ref(false)
const isLoggingIn = ref(false)
const hasError = ref(false)
const errorMessage = ref('')
const loadingText = ref('正在准备...')
const agreed = ref(true)
const showNewUserGuide = ref(false)
const newUserInfo = ref({
  nickname: ''
})

// 绑定相关状态（新增）
const showBindModal = ref(false)
const bindToken = ref('')
const isBinding = ref(false)

onMounted(async () => {
  console.log('🎉 授权页加载完成')
  
  // 检查是否已经登录
  const token = uni.getStorageSync('token')
  
  if (token) {
    console.log('✅ 检测到已有 Token，验证有效性...')
    
    // 验证 Token 是否有效
    const isValid = await validateToken()
    
    if (isValid) {
      loadingText.value = '正在跳转...'
      setTimeout(() => {
        redirectToHome()
      }, 500)
    } else {
      console.log('⚠️ Token 已过期，需要重新授权')
      clearError()
    }
  }
})

async function handleWechatLogin() {
  if (!agreed.value) {
    uni.showToast({ title: '请先同意用户协议', icon: 'none' })
    return
  }

  if (isLoggingIn.value) return
  
  isLoggingIn.value = true
  isLoading.value = true
  hasError.value = false
  loadingText.value = '正在获取微信授权...'

  try {
    console.log('🚀 开始微信自动登录...')
    
    const result = await wechatAutoLogin()

    if (result.needBind) {
      console.log('📋 需要绑定手机号，弹出绑定弹窗...')
      isLoading.value = false
      isLoggingIn.value = false
      
      bindToken.value = result.bindToken || ''
      showBindModal.value = true
      return
    }

    if (result.success) {
      loadingText.value = '登录成功，正在跳转...'
      
      uni.showToast({ 
        title: '登录成功', 
        icon: 'success',
        duration: 1000
      })

      setTimeout(() => {
        redirectToHome(result.role)
      }, 1000)

    } else {
      throw new Error(result.msg || '登录失败')
    }

  } catch (error: any) {
    console.error('❌ 登录失败:', error)
    
    hasError.value = true
    errorMessage.value = error.message || '登录失败，请重试'
    isLoading.value = false
    isLoggingIn.value = false

    uni.showToast({ 
      title: error.message || '登录失败', 
      icon: 'none',
      duration: 2000
    })

  } finally {
    setTimeout(() => {
      isLoading.value = false
      isLoggingIn.value = false
    }, 2000)
  }
}

function clearError() {
  hasError.value = false
  errorMessage.value = ''
}

/**
 * 关闭绑定弹窗
 */
function closeBindModal() {
  if (isBinding.value) return  // 绑定中不允许关闭
  
  showBindModal.value = false
  bindToken.value = ''
  
  console.log('🔒 已关闭绑定弹窗')
}

/**
 * 处理弹窗中的微信手机号授权
 */
async function handleModalGetPhoneNumber(e: any) {
  console.log('📱 弹窗中微信手机号授权结果:', e.detail.errMsg)
  
  // 场景 1：用户拒绝授权 或 个人版小程序无权限
  if (!e.detail.encryptedData || !e.detail.iv) {
    if (e.detail.errMsg?.includes('no permission')) {
      // 个人版小程序不支持 getPhoneNumber，自动跳转手动输入
      console.log('⚠️ 个人版小程序无手机号授权权限，自动跳转手动输入')
      uni.showToast({
        title: '请手动输入手机号',
        icon: 'none',
        duration: 1200
      })
      setTimeout(() => goToManualBind(), 1200)
    } else if (e.detail.errMsg?.includes('deny')) {
      uni.showToast({
        title: '已取消授权，可使用其他方式',
        icon: 'none',
        duration: 1500
      })
    } else {
      uni.showToast({
        title: '获取失败，请重试',
        icon: 'none'
      })
    }
    return
  }

  // 场景 2：用户同意授权，开始验证
  isBinding.value = true
  
  try {
    const result = await wechatBindPhone(
      bindToken.value,
      e.detail.encryptedData,
      e.detail.iv
    )
    
    console.log('✅ 手机号验证结果:', result)
    
    if (result.success && !result.needBind) {
      // ✅ 成功：手机号匹配
      handleBindSuccess(result)
    } else if (result.needBind) {
      // ❌ 不匹配：提示切换到手动方式
      handleBindMismatch(result)
    } else {
      throw new Error(result.msg || '验证失败')
    }
    
  } catch (error: any) {
    console.error('❌ 手机号验证异常:', error)
    
    uni.showModal({
      title: '验证失败',
      content: error.message || '网络异常，请稍后重试',
      confirmText: '使用其他手机号',
      cancelText: '返回',
      success: (res) => {
        if (res.confirm) {
          goToManualBind()
        }
        // 取消则留在弹窗中
      }
    })
    
  } finally {
    isBinding.value = false
  }
}

/**
 * 处理绑定成功
 */
function handleBindSuccess(result: any) {
  showBindModal.value = false
  
  uni.showToast({
    title: '绑定成功！',
    icon: 'success',
    duration: 1500
  })
  
  setTimeout(() => {
    redirectToHome(result.role)
  }, 1500)
}

/**
 * 处理绑定不匹配（提示用户切换方式）
 */
function handleBindMismatch(result: any) {
  const phone = result.decryptedPhone ? maskPhone(result.decryptedPhone) : ''
  
  uni.showModal({
    title: '手机号未注册',
    content: `您的微信手机号 ${phone} 未在当前机构中注册`,
    confirmText: '使用其他手机号',
    cancelText: '返回',
    success: (res) => {
      if (res.confirm) {
        goToManualBind()
      }
      // 取消则留在弹窗中
    }
  })
}

/**
 * 跳转到手动输入页
 */
function goToManualBind() {
  console.log('🔄 从弹窗跳转到手动输入页...')
  
  showBindModal.value = false
  
  uni.navigateTo({
    url: `/pages/bind/manual?bindToken=${encodeURIComponent(bindToken.value)}`
  })
}

/**
 * 手机号脱敏处理
 */
function maskPhone(phone: string): string {
  if (!phone || phone.length !== 11) return phone
  return phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2')
}

function showAgreement() {
  uni.showModal({
    title: '用户服务协议',
    content: '这里是用户协议的内容...',
    showCancel: false,
    confirmText: '我知道了'
  })
}

function showPrivacy() {
  uni.showModal({
    title: '隐私政策',
    content: '这里是隐私政策的内容...',
    showCancel: false,
    confirmText: '我知道了'
  })
}

function closeNewUserGuide() {
  showNewUserGuide.value = false
  redirectToHome()
}

async function completeNewUserGuide() {
  if (!newUserInfo.value.nickname.trim()) {
    uni.showToast({ title: '请输入称呼', icon: 'none' })
    return
  }

  uni.showLoading({ title: '保存中...' })
  
  try {
    // TODO: 调用 API 保存用户信息
    // await userApi.updateProfile({ nickname: newUserInfo.value.nickname })
    
    uni.hideLoading()
    showNewUserGuide.value = false
    
    uni.showToast({ 
      title: '欢迎加入！', 
      icon: 'success' 
    })
    
    setTimeout(() => {
      redirectToHome()
    }, 1000)

  } catch (error) {
    uni.hideLoading()
    uni.showToast({ title: '保存失败', icon: 'none' })
  }
}
</script>

<style lang="scss">
/* ✅ 使用 Design System 全局变量和 Mixins */

.auth-container {
  min-height: 100vh;
  position: relative;
  overflow: hidden;
  background: $background-primary;
}

// 背景层 - 高级轻奢风格
.bg-layer {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 0;

  .gradient-bg {
    position: absolute;
    width: 100%;
    height: 100%;
    background: $gradient-page;  // 米白色渐变
  }

  // 柔和光晕装饰（替代原来的强光效）
  .light-orb {
    position: absolute;
    border-radius: 50%;
    filter: blur(120rpx);  // 更柔和的模糊
    opacity: 0.15;         // 降低透明度
    animation: gentleFloat 12s ease-in-out infinite;  // 更慢的动画

    &.orb-1 {
      width: 500rpx;
      height: 500rpx;
      background: radial-gradient(circle, rgba(201, 166, 107, 0.25), transparent);  // 香槟金色
      top: -150rpx;
      right: -150rpx;
      animation-delay: 0s;
    }

    &.orb-2 {
      width: 400rpx;
      height: 400rpx;
      background: radial-gradient(circle, rgba(217, 167, 176, 0.2), transparent);   // 莫兰迪粉色
      bottom: 15%;
      left: -120rpx;
      animation-delay: -4s;
    }

    &.orb-3 {
      width: 350rpx;
      height: 350rpx;
      background: radial-gradient(circle, rgba(232, 196, 138, 0.18), transparent);  // 浅金色
      bottom: -80rpx;
      right: 18%;
      animation-delay: -7s;
    }
  }

  .grid-overlay {
    position: absolute;
    width: 100%;
    height: 100%;
    background-image: 
      linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
    background-size: 60rpx 60rpx;
  }
}

@keyframes float {
  0%, 100% {
    transform: translateY(0) scale(1);
  }
  50% {
    transform: translateY(-30rpx) scale(1.05);
  }
}

// 主内容区
.main-content {
  position: relative;
  z-index: 1;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: $space-3xl;  // 更大的留白
  box-sizing: border-box;
}

// 品牌区域 - 高级优雅风
.brand-section {
  text-align: center;
  margin-bottom: $space-2xl;  // 增加间距
  animation: elegantFadeIn 1s $ease-elegant both;

  .brand-logo {
    width: 180rpx;           // 稍大的Logo
    height: 180rpx;
    margin: 0 auto $space-xl;
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;

    // 柔和光晕效果（香槟金色）
    .logo-glow {
      position: absolute;
      width: 100%;
      height: 100%;
      background: radial-gradient(circle, rgba(201, 166, 107, 0.2), transparent);  // 香槟金
      border-radius: 50%;
      animation: gentlePulse 3s $ease-in-out infinite;
    }

    .logo-icon {
      font-size: 80rpx;     // 稍大的图标
      position: relative;
      z-index: 1;
      filter: drop-shadow(0 4rpx 12rpx rgba(201, 166, 107, 0.15));  // 轻微阴影
    }
  }

  .brand-name {
    display: block;
    font-family: $font-family-display;  // 使用衬线字体
    font-size: $font-size-display;
    font-weight: $font-weight-bold;
    color: $text-primary;
    margin-bottom: $space-sm;
    letter-spacing: 6rpx;   // 增加字间距（更高级）
    text-transform: uppercase;  // 大写（可选，更显高端）
  }

  .brand-slogan {
    display: block;
    font-size: $font-size-body-lg;
    font-weight: $font-weight-medium;                    // 中等字重（更清晰）
    letter-spacing: $letter-spacing-wider;               // 加宽字间距（优雅感）
    margin-bottom: $space-md;
    background: linear-gradient(
      135deg,
      $primary-solid 0%,
      $accent-solid 50%,
      $primary-solid 100%
    );                                                    // 香槟金→莫兰迪粉渐变
    -webkit-background-clip: text;                       // iOS Safari 兼容
    -webkit-text-fill-color: transparent;                // 渐变文字效果
    background-clip: text;
    animation: sloganShimmer 4s ease-in-out infinite;    // 微光动画
  }

  @keyframes sloganShimmer {
    0%, 100% {
      opacity: 0.9;
      filter: brightness(1);
    }
    50% {
      opacity: 1;
      filter: brightness(1.15);                          // 微微提亮
    }
  }

  // 品牌装饰线（香槟金色渐变）
  .brand-line {
    width: 140rpx;          // 稍长
    height: 3rpx;           // 更细
    background: linear-gradient(90deg, transparent, $primary-solid, transparent);  // 香槟金
    margin: 0 auto;
    border-radius: 2rpx;
    opacity: 0.8;           // 略透明
  }
}

// ========== 高级轻奢动画系统 ==========

@keyframes fadeInDown {
  from {
    opacity: 0;
    transform: translateY(-30rpx);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

// 优雅淡入（Apple风格）
@keyframes elegantFadeIn {
  from {
    opacity: 0;
    transform: translateY(-20rpx) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

// 柔和脉冲（替代原来的强脉冲）
@keyframes gentlePulse {
  0%, 100% {
    transform: scale(1);
    opacity: 0.15;   // 更透明
  }
  50% {
    transform: scale(1.08);  // 更小的缩放
    opacity: 0.25;
  }
}

// 轻柔浮动（用于背景光晕）
@keyframes gentleFloat {
  0%, 100% {
    transform: translate(0, 0) scale(1);
  }
  33% {
    transform: translate(30rpx, -20rpx) scale(1.02);
  }
  66% {
    transform: translate(-20rpx, 15rpx) scale(0.98);
  }
}

// 授权卡片 - 高级卡片设计
.auth-card-wrapper {
  width: 100%;
  max-width: 620rpx;       // 稍宽
  animation: elegantSlideUp 1s $ease-elegant 0.3s both;  // 更优雅的入场
}

.auth-card {
  background: rgba(255, 255, 255, 0.95);  // 近乎纯白，高质感
  backdrop-filter: blur(40rpx);           // 更强的模糊
  -webkit-backdrop-filter: blur(40rpx);
  border: 1rpx solid rgba(201, 166, 107, 0.15);  // 香槟金色细边框
  border-radius: $radius-2xl;
  padding: $space-2xl $space-xl;          // 更大的内边距
  box-shadow: $shadow-modal;              // 使用新的柔和阴影
  position: relative;
  overflow: hidden;
  transition: all $duration-normal $ease-standard;

  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(
      135deg,
      rgba(255, 255, 255, 0.1) 0%,
      rgba(255, 255, 255, 0.02) 100%
    );
    pointer-events: none;
  }

  .card-glow {
    position: absolute;
    width: 200rpx;
    height: 200rpx;
    background: radial-gradient(circle, rgba(102, 126, 234, 0.15), transparent);
    top: -60rpx;
    right: -60rpx;
    border-radius: 50%;
    pointer-events: none;
  }

  &.card-loading {
    border-color: rgba(102, 126, 234, 0.3);
  }

  &.card-error {
    border-color: rgba(239, 68, 68, 0.3);
    animation: shake 0.5s ease-in-out;
  }
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30rpx);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-10rpx); }
  75% { transform: translateX(10rpx); }
}

// 用户信息展示区
.user-info-area {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 180rpx;
  margin-bottom: $space-xl;
  position: relative;
  z-index: 1;

  .avatar-placeholder {
    width: 140rpx;
    height: 140rpx;
    border-radius: 50%;
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.2), rgba(118, 75, 162, 0.2));
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;

    .avatar-icon {
      font-size: 64rpx;
      opacity: 0.7;
    }

    .avatar-ring {
      position: absolute;
      width: 100%;
      height: 100%;
      border: 2rpx solid rgba(102, 126, 234, 0.3);
      border-radius: 50%;
      animation: ring-pulse 2s ease-in-out infinite;
    }
  }

  @keyframes ring-pulse {
    0%, 100% {
      transform: scale(1);
      opacity: 0.3;
    }
    50% {
      transform: scale(1.08);
      opacity: 0.6;
    }
  }

  .loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: $space-md;

    .loading-spinner {
      width: 60rpx;
      height: 60rpx;
      border: 4rpx solid rgba(102, 126, 234, 0.2);
      border-top-color: $primary-solid;
      border-radius: 50%;
      animation: spin 1s linear infinite;
    }

    .loading-text {
      font-size: $font-size-body_sm;
      color: $text-secondary;
    }
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .error-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: $space-sm;

    .error-icon {
      font-size: 56rpx;
    }

    .error-text {
      font-size: $font-size-body_sm;
      color: $color-danger;
      text-align: center;
      max-width: 400rpx;
    }
  }
}

// 操作按钮区域
.action-buttons {
  margin-bottom: $space-lg;
  position: relative;
  z-index: 1;

  // 微信登录按钮 - 高级轻奢风格
  .wechat-login-btn {
    width: 100%;
    height: $button-height-lg;     // 使用新的标准高度
    background: linear-gradient(135deg, $wechat-green 0%, $wechat-green-light 100%);  // 微信绿色（保留）
    border-radius: 50rpx;          // 近胶囊形，更精致
    border: none;
    color: #fff;
    font-size: $font-size-h4;
    font-weight: $font-weight-semibold;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
    transition: all $duration-normal $ease-standard;
    box-shadow: $shadow-button;     // 使用新的香槟金阴影系统

    &:active {
      transform: scale(0.98) translateY(2rpx);  // 更细腻的点击反馈
      box-shadow: $shadow-button-hover;
    }

    &.btn-disabled {
      opacity: 0.5;               // 更透明
      cursor: not-allowed;
      filter: grayscale(20%);     // 轻微灰化
    }

    .btn-content {
      display: flex;
      align-items: center;
      gap: $space-sm;
      position: relative;
      z-index: 1;

      .wechat-btn-icon {
        font-size: $icon-size-lg;   // 使用标准图标尺寸
      }

      .wechat-btn-text {
        letter-spacing: 3rpx;       // 增加字间距
        font-weight: $font-weight-semibold;
      }
    }

    // 高光扫过效果（更精致）
    .btn-shine {
      position: absolute;
      top: 0;
      left: -150%;                  // 从更远的位置开始
      width: 60%;
      height: 100%;
      background: linear-gradient(
        90deg,
        transparent,
        rgba(255, 255, 255, 0.25),  // 降低透明度
        transparent
      );
      animation: shimmerSlide 4s $ease-in-out infinite;  // 改为持续动画
    }
  }

  // 加载状态按钮
  .loading-btn {
    width: 100%;
    height: $button-height-lg;
    background: linear-gradient(135deg, rgba(201, 166, 107, 0.15), rgba(217, 167, 176, 0.15));  // 香槟金+粉色
    border-radius: 50rpx;
    border: 2rpx solid rgba(201, 166, 107, 0.25);
    color: $primary-solid;           // 香槟金色文字
    font-size: $font-size-body_lg;
    display: flex;
    align-items: center;
    justify-content: center;

    .btn-loading-content {
      display: flex;
      align-items: center;
      gap: $space-sm;

      .mini-spinner {
        width: 36rpx;
        height: 36rpx;
        border: 3rpx solid rgba(201, 166, 107, 0.25);
        border-top-color: $primary-solid;  // 香槟金色旋转边框
        border-radius: 50%;
        animation: elegantSpin 1.2s $ease-in-out infinite;
      }
    }
  }
}

// 协议提示
.agreement-hint {
  display: flex;
  align-items: flex-start;
  gap: $space-xs;
  position: relative;
  z-index: 1;

  .checkbox-wrapper {
    flex-shrink: 0;
    padding-top: 4rpx;
  }

  .custom-checkbox {
    width: 32rpx;
    height: 32rpx;
    border: 2rpx solid rgba(255, 255, 255, 0.3);
    border-radius: 6rpx;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s ease;
    background: rgba(255, 255, 255, 0.05);

    &.checked {
      background: $primary-solid;
      border-color: $primary-solid;

      .check-mark {
        color: #fff;
        font-size: 20rpx;
        font-weight: bold;
      }
    }
  }

  .agreement-text {
    flex: 1;
    font-size: $font-size-tiny;
    color: $text-muted;
    line-height: 1.5;

    .link {
      color: $primary-light;
      text-decoration: underline;
    }
  }
}

// ========== 绑定弹窗样式（V3.0 - 高级轻奢版）==========

.bind-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: $bg-overlay;           // 使用新的半透明遮罩
  backdrop-filter: blur(20rpx);     // 更强的模糊
  -webkit-backdrop-filter: blur(20rpx);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  z-index: $z-maximum;
  animation: elegantFadeIn $duration-slow $ease-elegant;  // 使用优雅动画

  .bind-modal-content {
    width: 100%;
    max-height: 85vh;
    background: $gradient-modal;   // 米白色渐变背景
    border-radius: $radius-3xl $radius-3xl 0 0;
    padding: 0 $space-xl calc($safe-area-bottom + $space-lg);
    animation: elegantSlideUp $duration-slow $ease-spring;  // 弹性入场
    box-shadow: $shadow-modal;     // 柔和阴影
    display: flex;
    flex-direction: column;
    overflow-y: auto;

    // ===== 1. 拖拽指示器（香槟金色）=====
    .drag-indicator {
      width: 64rpx;
      height: 5rpx;
      background: linear-gradient(90deg, transparent, $primary-solid, transparent);  // 香槟金渐变
      border-radius: 3rpx;
      margin: $space-md auto $space-xl;
      opacity: 0.4;               // 更透明
      flex-shrink: 0;
    }

    // ===== 2. 品牌视觉区域（视觉锚点）=====
    .brand-visual-area {
      display: flex;
      flex-direction: column;
      align-items: center;
      margin-bottom: $space-xl;
      flex-shrink: 0;

      .brand-logo-container {
        width: 130rpx;             // 稍大
        height: 130rpx;
        position: relative;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: $space-md;

        // 光晕环动画（香槟金色调）
        .logo-glow-ring {
          position: absolute;
          border-radius: 50%;
          border: 2rpx solid;

          &.ring-1 {
            width: 100%;
            height: 100%;
            border-color: rgba(201, 166, 107, 0.2);  // 香槟金
            animation: gentleGlowRing 4s $ease-in-out infinite;
          }

          &.ring-2 {
            width: 135%;
            height: 135%;
            border-color: rgba(217, 167, 176, 0.15);  // 莫兰迪粉
            animation: gentleGlowRing 4s $ease-in-out infinite 0.7s;
          }
        }

        .brand-logo-emoji {
          font-size: 60rpx;
          position: relative;
          z-index: 2;
          filter: drop-shadow(0 4rpx 16rpx rgba(201, 166, 107, 0.2));  // 金色阴影
        }
      }

      // 装饰渐变线（香槟金色）
      .decorative-line {
        width: 80rpx;
        height: 3rpx;
        background: linear-gradient(90deg, transparent, $primary-solid, transparent);
        border-radius: 2rpx;
        opacity: 0.5;
      }
    }

    // ===== 3. 信息区域（标题+说明）=====
    .info-section {
      text-align: center;
      margin-bottom: $space-xl;
      flex-shrink: 0;

      .main-title {
        display: block;
        font-family: $font-family-display;  // 衬线字体
        font-size: $font-size-h2;
        font-weight: $font-weight-bold;
        color: $text-primary;
        margin-bottom: $space-xs;
        letter-spacing: 1rpx;
        line-height: $line-height-snug;
      }

      .sub-description {
        display: block;
        font-size: $font-size-body_sm;
        color: $text-secondary;     // 新中性色
        line-height: $line-height-relaxed;
        letter-spacing: 0.3rpx;
        font-weight: $font-weight-light;
      }
    }

    // ===== 4. 主操作区：微信一键授权 =====
    .primary-action-zone {
      margin-bottom: $space-lg;
      flex-shrink: 0;

      .wechat-auth-btn {
        width: 100%;
        height: $button-height-lg;   // 标准高度
        background: linear-gradient(135deg, $wechat-green 0%, $wechat-green-light 100%) !important;
        border-radius: 50rpx;         // 近胶囊形
        border: none !important;
        position: relative;
        overflow: hidden;
        box-shadow: $shadow-button;   // 柔和阴影

        &::after {
          display: none !important;
        }

        // 正常状态内容
        .btn-main-content {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: $space-sm;
          height: 100%;

          .wechat-icon-box {
            width: $icon-size-md;
            height: $icon-size-md;
            display: flex;
            align-items: center;
            justify-content: center;

            .wechat-icon-symbol {
              font-size: $icon-size-lg;
            }
          }

          .auth-btn-label {
            color: #ffffff;
            font-size: $font-size-h4;
            font-weight: $font-weight-semibold;
            letter-spacing: 2rpx;
          }

          // 高光扫过效果
          .btn-highlight-effect {
            position: absolute;
            top: 0;
            left: -150%;
            width: 60%;
            height: 100%;
            background: linear-gradient(
              90deg,
              transparent,
              rgba(255, 255, 255, 0.25),
              transparent
            );
            animation: shimmerSlide 4s $ease-in-out infinite;
          }
        }

        // 加载状态
        .btn-loading-state {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: $space-sm;
          height: 100%;

          .loading-spinner-mini {
            width: 36rpx;
            height: 36rpx;
            border: 3rpx solid rgba(255, 255, 255, 0.3);
            border-top-color: #ffffff;
            border-radius: 50%;
            animation: elegantSpin 1s $ease-in-out infinite;
          }

          .loading-text {
            color: #ffffff;
            font-size: $font-size-body_lg;
            font-weight: $font-weight-medium;
          }
        }

        // 状态变体
        &.is-loading {
          opacity: 0.92;
          box-shadow: $shadow-button;   // 更新：使用香槟金阴影（替代绿色）
        }

        &:active:not(.is-loading) {
          transform: scale(0.97) translateY(2rpx);
          box-shadow: $shadow-sm;   // 更柔和的阴影
          transition: all $duration-fast $ease-standard;
        }
      }
    }

    // ===== 5. 次级操作区：分隔线 + 其他手机号 =====
    .secondary-action-zone {
      margin-bottom: $space-md;
      flex-shrink: 0;

      // 轻量分隔线（香槟金色调）
      .light-divider {
        display: flex;
        align-items: center;
        gap: $space-md;
        margin-bottom: $space-md;

        .divider-segment {
          flex: 1;
          height: 1rpx;
          background: linear-gradient(
            90deg,
            transparent,
            $divider-color,
            transparent
          );
        }

        .divider-label {
          font-size: $font-size-overline;
          color: $text-tertiary;     // 新中性色
          font-weight: $font-weight-medium;
          letter-spacing: 1.5rpx;    // 更宽的字间距
        }
      }

      // 其他手机号触发器（优雅弱化）
      .manual-bind-trigger {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: $padding-md $padding-lg;
        background: $gradient-card;  // 卡片渐变背景
        border: 1rpx solid $border-light;
        border-radius: $radius-lg;
        transition: all $duration-fast $ease-standard;

        &:active {
          background: $bg-secondary;  // 激活时变暗
          border-color: $border-normal;
          transform: scale(0.985);
          box-shadow: $shadow-xs;     // 轻微阴影
        }

        .trigger-label {
          font-size: $font-size-body_lg;
          color: $text-secondary;     // 新中性色
          font-weight: $font-weight-medium;
          letter-spacing: 0.5rpx;
        }

        .trigger-arrow {
          font-size: $font-size-h4;
          color: $primary-solid;      // 香槟金色箭头
          font-weight: $font-weight-semibold;
          margin-left: $space-sm;
          transition: transform $duration-fast $ease-standard;
          
          // 箭头动画（可选）
          .manual-bind-trigger:hover & {
            transform: translateX(4rpx);
          }
        }
      }
    }

    // ===== 6. 弱提示：小型内联提示（柔和色调）=====
    .inline-hint {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: $space-xs;
      padding: $padding-sm $padding-md;
      background: rgba(212, 167, 106, 0.08);  // 暖色调背景（替代黄色）
      border-radius: $radius-md;
      border: 1rpx solid $warning-border;       // 使用新的边框变量
      flex-shrink: 0;

      .hint-icon {
        font-size: $font-size-caption;
        line-height: 1;
        flex-shrink: 0;
      }

      .hint-text {
        font-size: $font-size-tiny;             // 更小的文字
        color: $warning-color;                   // 使用新的警告色
        line-height: $line-height-relaxed;
        letter-spacing: 0.3rpx;
      }
    }
  }
}

// ========== 动画关键帧（高级轻奢版）==========

// 遮罩层淡入
@keyframes overlayFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

// 内容上滑（已替换为 elegantSlideUp）
@keyframes contentSlideUp {
  from {
    transform: translateY(100%);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

// 柔和光晕环脉冲（用于Logo装饰）
@keyframes gentleGlowRing {
  0%, 100% {
    transform: scale(1);
    opacity: 0.12;   // 更透明
  }
  50% {
    transform: scale(1.06);  // 更小的缩放
    opacity: 0.2;
  }
}

// 按钮高光扫过（保留兼容）
@keyframes btnShineSweep {
  0% { left: -100%; }
  15%, 100% { left: 150%; }
}

@keyframes spinnerRotate {
  to { transform: rotate(360deg); }
}

// ========== 新增高级轻奢动画 ==========

// 优雅旋转（用于加载状态）
@keyframes elegantSpin {
  0% { 
    transform: rotate(0deg);
    opacity: 0.8;
  }
  50% {
    opacity: 1;
  }
  100% { 
    transform: rotate(360deg);
    opacity: 0.8;
  }
}

// 高光扫过（用于按钮）
@keyframes shimmerSlide {
  0% { 
    left: -150%; 
  }
  20%, 100% { 
    left: 150%; 
  }
}

// 优雅上滑（用于卡片入场）
@keyframes elegantSlideUp {
  from {
    opacity: 0;
    transform: translateY(40rpx) scale(0.98);
    filter: blur(10rpx);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
    filter: blur(0);
  }
}

// 底部信息 - 高级轻奢风格
.footer-info {
  margin-top: $space-2xl;           // 更大的间距
  text-align: center;
  animation: elegantFadeIn 1.2s $ease-elegant 0.6s both;  // 延迟入场

  .footer-brand {
    display: block;
    font-family: $font-family-display;  // 衬线字体（优雅感）
    font-size: $font-size-body-sm;      // 稍大一点（更易读）
    font-weight: $font-weight-medium;   // 中等字重
    color: $primary-solid;              // 使用香槟金色
    letter-spacing: $letter-spacing-wider;  // 加宽字间距
    margin-bottom: $space-xs;
    background: linear-gradient(
      90deg,
      $primary-solid 0%,
      $accent-light 100%
    );                                    // 香槟金→浅粉渐变
    -webkit-background-clip: text;       // iOS Safari 兼容
    -webkit-text-fill-color: transparent;// 渐变文字效果
    background-clip: text;
    opacity: 0.85;                       // 适度透明度
  }

  .version-info {
    .version-text {
      font-size: $font-size-tiny;
      color: rgba(142, 133, 121, 0.4);  // 暖灰色调（替代纯白）
      letter-spacing: 1rpx;
    }
  }
}

// 新用户引导弹窗
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: $space-xl;
  animation: fadeIn 0.3s ease;
}

.modal-content {
  width: 100%;
  max-width: 560rpx;
  background: $background-primary;
  border-radius: $radius-2xl;
  padding: $space-xl * 1.5;
  animation: modalSlideUp 0.3s ease;

  .modal-title {
    display: block;
    font-size: $font-size-h3;
    font-weight: $font-weight-bold;
    color: $text-primary;
    text-align: center;
    margin-bottom: $space-sm;
  }

  .modal-desc {
    display: block;
    font-size: $font-size-body;
    color: $text-secondary;
    text-align: center;
    margin-bottom: $space-xl;
  }

  .form-item {
    margin-bottom: $space-xl;

    .modal-input {
      width: 100%;
      height: 88rpx;
      background: rgba(255, 255, 255, 0.05);
      border: 2rpx solid rgba(255, 255, 255, 0.1);
      border-radius: $radius-lg;
      padding: 0 $space-lg;
      font-size: $font-size-body;
      color: $text-primary;
      box-sizing: border-box;

      &:focus {
        border-color: $primary-solid;
        background: rgba(102, 126, 234, 0.05);
      }
    }
  }

  .modal-actions {
    display: flex;
    gap: $space-md;

    .modal-btn {
      flex: 1;
      height: 88rpx;
      border-radius: $radius-lg;
      border: none;
      font-size: $font-size-body;
      font-weight: $font-weight-semibold;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s ease;

      &.secondary {
        background: rgba(255, 255, 255, 0.05);
        color: $text-secondary;
        border: 2rpx solid rgba(255, 255, 255, 0.1);

        &:active {
          background: rgba(255, 255, 255, 0.1);
        }
      }

      &.primary {
        background: linear-gradient(135deg, $primary-solid, $primary-dark);
        color: #fff;
        box-shadow: 0 4rpx 16rpx rgba(102, 126, 234, 0.3);

        &:active {
          transform: scale(0.98);
        }
      }
    }
  }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes modalSlideUp {
  from {
    opacity: 0;
    transform: translateY(40rpx);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>