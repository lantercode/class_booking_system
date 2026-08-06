<template>
  <view class="page">
    <view class="header">
      <view class="logo">
        <text class="logo-icon">💃</text>
      </view>
      <text class="title">舞蹈约课</text>
      <text class="subtitle">发现精彩课程</text>
    </view>

    <view class="form-container">
      <view class="form-item">
        <view class="input-wrap">
          <text class="input-icon">📱</text>
          <input class="input-field" placeholder="请输入手机号" v-model="phone" type="number" maxlength="11" />
        </view>
      </view>

      <view class="form-item">
        <view class="input-wrap">
          <text class="input-icon">🔐</text>
          <input class="input-field" placeholder="请输入密码" v-model="password" type="password" />
        </view>
      </view>

      <view class="form-item">
        <view class="input-wrap">
          <text class="input-icon">🏢</text>
          <picker mode="selector" :range="tenants" range-key="name" @change="handleTenantChange">
            <view class="picker-field">
              <text>{{ selectedTenant?.name || '请选择机构' }}</text>
              <text class="picker-arrow">›</text>
            </view>
          </picker>
        </view>
      </view>

      <view class="login-btn" :class="{ disabled: !canLogin }" @click="handleLogin">
        <text>{{ loading ? '登录中...' : '登录' }}</text>
      </view>

      <view class="quick-links">
        <text class="link-item" @click="goToRegister">注册</text>
        <text class="link-divider">|</text>
        <text class="link-item" @click="handleForgotPassword">忘记密码</text>
      </view>
    </view>

    <view class="wx-login">
      <view class="wx-btn" @click="handleWxLogin">
        <text class="wx-icon">💬</text>
        <text>微信快捷登录</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { authApi } from '@/api'

const phone = ref('')
const password = ref('')
const loading = ref(false)

const tenants = ref([
  { name: '舞蹈工作室', slug: 'dance-studio' },
  { name: '艺术培训中心', slug: 'art-center' },
  { name: '健身俱乐部', slug: 'fitness-club' }
])

const selectedTenant = ref(tenants.value[0])

const canLogin = computed(() => {
  return phone.value.length === 11 && password.value.length >= 6 && selectedTenant.value
})

function handleTenantChange(e: any) {
  selectedTenant.value = tenants.value[e.detail.value]
}

async function handleLogin() {
  if (!canLogin.value || loading.value) return
  loading.value = true
  try {
    const res = await authApi.login({
      phone: phone.value,
      password: password.value,
      tenant_slug: selectedTenant.value.slug
    })
    uni.setStorageSync('token', res.data.access_token)
    uni.setStorageSync('refresh_token', res.data.refresh_token)
    uni.showToast({ title: '登录成功', icon: 'success' })
    setTimeout(() => {
      uni.switchTab({ url: '/pages/index/index' })
    }, 1500)
  } catch (e: any) {
    uni.showToast({ title: e?.response?.data?.msg || '登录失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function goToRegister() {
  uni.showToast({ title: '注册功能开发中', icon: 'none' })
}

function handleForgotPassword() {
  uni.showToast({ title: '找回密码功能开发中', icon: 'none' })
}

function handleWxLogin() {
  uni.showToast({ title: '微信登录功能开发中', icon: 'none' })
}
</script>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 60rpx 30rpx;
  display: flex;
  flex-direction: column;
}
.header {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60rpx 0;
}
.logo {
  width: 120rpx;
  height: 120rpx;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 30rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}
.logo-icon {
  font-size: 60rpx;
}
.title {
  font-size: 48rpx;
  font-weight: bold;
  color: #fff;
  margin-top: 30rpx;
}
.subtitle {
  font-size: 28rpx;
  color: rgba(255, 255, 255, 0.8);
  margin-top: 12rpx;
}
.form-container {
  flex: 1;
  background: #fff;
  border-radius: 30rpx;
  padding: 40rpx;
  margin-top: 20rpx;
}
.form-item {
  margin-bottom: 30rpx;
}
.input-wrap {
  display: flex;
  align-items: center;
  padding: 24rpx;
  background: #f8f9fa;
  border-radius: 16rpx;
}
.input-icon {
  font-size: 32rpx;
  margin-right: 20rpx;
}
.input-field {
  flex: 1;
  font-size: 30rpx;
}
.picker-field {
  flex: 1;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 30rpx;
  color: #333;
}
.picker-arrow {
  font-size: 36rpx;
  color: #999;
}
.login-btn {
  width: 100%;
  padding: 28rpx;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 30rpx;
  text-align: center;
  font-size: 32rpx;
  color: #fff;
  margin-top: 20rpx;
}
.login-btn.disabled {
  background: #ccc;
}
.quick-links {
  display: flex;
  justify-content: center;
  align-items: center;
  margin-top: 30rpx;
}
.link-item {
  font-size: 26rpx;
  color: #999;
}
.link-divider {
  margin: 0 20rpx;
  color: #ddd;
}
.wx-login {
  padding: 40rpx 0;
}
.wx-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16rpx;
  padding: 28rpx;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 30rpx;
  font-size: 30rpx;
  color: #333;
}
.wx-icon {
  font-size: 36rpx;
}
</style>