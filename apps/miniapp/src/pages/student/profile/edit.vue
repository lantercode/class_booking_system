<template>
  <view class="edit-page">

    <!-- 主内容区域 -->
    <view class="main-content">
      <scroll-view scroll-y class="form-scroll" :show-scrollbar="false">
        <view class="form-card">
          <!-- 头像区域 -->
          <view class="avatar-section">
            <text class="section-label">头像</text>
            <view class="avatar-wrapper" @tap="changeAvatar">
              <view class="avatar">
                <text class="avatar-text">{{ form.nickname?.charAt(0) || '?' }}</text>
              </view>
              <view class="camera-badge">
                <text class="camera-icon">📷</text>
              </view>
            </view>
          </view>

          <!-- 姓名输入 -->
          <view class="form-item">
            <text class="label">姓名 *</text>
            <input
              v-model="form.nickname"
              type="text"
              placeholder="请输入姓名"
              class="input-field"
              :class="{ 'input-error': errors.nickname }"
              @blur="validateNickname"
            />
            <text v-if="errors.nickname" class="error-msg">{{ errors.nickname }}</text>
          </view>

          <!-- 手机号（只读） -->
          <view class="form-item">
            <text class="label">手机号</text>
            <input
              v-model="form.phone"
              type="number"
              class="input-field input-disabled"
              disabled
              placeholder="手机号"
            />
          </view>

          <!-- 简介文本域 -->
          <view class="form-item">
            <text class="label">简介</text>
            <textarea
              v-model="form.bio"
              placeholder="介绍一下自己..."
              class="textarea-field"
              :maxlength="200"
            />
            <text class="char-count">{{ form.bio?.length || 0 }}/200</text>
          </view>
        </view>
      </scroll-view>
    </view>

    <!-- 底部保存按钮 -->
    <view class="footer-area">
      <button
        class="save-btn"
        :class="{ 'btn-disabled': !isFormValid }"
        :disabled="!isFormValid || isLoading"
        @tap="handleSubmit"
      >
        <text v-if="isLoading" class="btn-loading">⏳</text>
        <text>{{ isLoading ? '保存中...' : '保存修改' }}</text>
      </button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { userApi } from '@/api'

const isLoading = ref(false)

const form = reactive({
  nickname: '',
  phone: '',
  bio: ''
})

const errors = reactive({
  nickname: ''
})

const isFormValid = computed(() => {
  return form.nickname.trim()
})

onMounted(() => {
  loadUserInfo()
})

const loadUserInfo = () => {
  const info = uni.getStorageSync('user_info')
  if (info) {
    const user = JSON.parse(info)
    form.nickname = user.nickname || ''
    form.phone = user.phone || ''
    form.bio = user.bio || ''
  }
}

const validateNickname = () => {
  errors.nickname = form.nickname.trim() ? '' : '请输入姓名'
}

const changeAvatar = () => {
  uni.showToast({ title: '头像上传功能开发中', icon: 'none' })
}

const handleSubmit = async () => {
  validateNickname()

  if (!isFormValid.value) return

  isLoading.value = true
  try {
    const result = await userApi.update({
      nickname: form.nickname,
      bio: form.bio
    })

    if (result.code === 0 || result.code === 200) {
      const userInfo = JSON.parse(uni.getStorageSync('user_info'))
      userInfo.nickname = form.nickname
      userInfo.bio = form.bio
      uni.setStorageSync('user_info', JSON.stringify(userInfo))

      uni.showToast({ title: '保存成功', icon: 'success' })
      setTimeout(() => uni.navigateBack(), 1500)
    } else {
      uni.showToast({ title: result.msg || '保存失败', icon: 'none' })
    }
  } catch {
    uni.showToast({ title: '保存失败', icon: 'none' })
  } finally {
    isLoading.value = false
  }
}

const goBack = () => {
  uni.navigateBack()
}
</script>

<style lang="scss" scoped>

.edit-page {
  @include page-container($bg-primary);
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.form-scroll {
  flex: 1;
  height: 0;
  padding: $space-lg $space-md;
  padding-bottom: 180rpx;
}

// 表单卡片 - 使用玻璃态效果（与首页统一）
.form-card {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20rpx);
  -webkit-backdrop-filter: blur(20rpx);
  border-radius: $radius-xl;
  padding: $space-lg;
  box-shadow: $shadow-card;
  border: 1rpx solid $border-subtle;
}

// 头像区域
.avatar-section {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: $space-xl;
  padding-bottom: $space-lg;
  border-bottom: 1rpx solid $border-subtle;
}

.section-label {
  font-size: $font-size-body;
  color: $text-primary;
  font-weight: $font-weight-medium;
}

.avatar-wrapper {
  position: relative;
  width: 140rpx;
  height: 140rpx;
}

.avatar {
  width: 100%;
  height: 100%;
  border-radius: $radius-full;
  background: $primary-gradient;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8rpx 24rpx rgba(102, 126, 234, 0.25);
}

.avatar-text {
  font-size: 52rpx;
  color: #fff;
  font-weight: $font-weight-bold;
}

.camera-badge {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 44rpx;
  height: 44rpx;
  background: #fff;
  border-radius: $radius-full;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: $shadow-sm;
  border: 2rpx solid $border-light;
}

.camera-icon {
  font-size: 22rpx;
}

// 表单项
.form-item {
  margin-bottom: $space-lg;

  &:last-child {
    margin-bottom: 0;
  }
}

.label {
  font-size: $font-size-body_sm;
  color: $text-secondary;
  margin-bottom: $space-sm;
  display: block;
  font-weight: $font-weight-medium;
}

// 输入框 - 统一样式
.input-field {
  width: 100%;
  height: 88rpx;
  background: $bg-secondary;
  border: 2rpx solid $border-light;
  border-radius: $radius-md;
  padding: 0 $space-md;
  font-size: $font-size-body;
  color: $text-primary;
  transition: all $duration-fast $ease-standard;

  &:focus {
    border-color: $primary-solid;
    box-shadow: 0 0 0 4rpx rgba(102, 126, 234, 0.1);
    background: #fff;
  }

  &.input-error {
    border-color: $error-color;
    background: rgba($error-color, 0.05);
  }

  &.input-disabled {
    background: $bg-tertiary;
    color: $text-tertiary;
    cursor: not-allowed;
  }
}

.error-msg {
  font-size: $font-size-caption;
  color: $error-color;
  margin-top: $space-xs;
  display: block;
}

// 文本域
.textarea-field {
  width: 100%;
  height: 180rpx;
  background: $bg-secondary;
  border: 2rpx solid $border-light;
  border-radius: $radius-md;
  padding: $space-md;
  font-size: $font-size-body;
  color: $text-primary;
  transition: all $duration-fast $ease-standard;

  &:focus {
    border-color: $primary-solid;
    box-shadow: 0 0 0 4rpx rgba(102, 126, 234, 0.1);
    background: #fff;
  }
}

.char-count {
  font-size: $font-size-caption;
  color: $text-tertiary;
  text-align: right;
  margin-top: $space-xs;
  display: block;
}

// 底部区域
.footer-area {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: $space-md $space-lg;
  padding-bottom: calc($space-lg + env(safe-area-inset-bottom));
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20rpx);
  -webkit-backdrop-filter: blur(20rpx);
  border-top: 1rpx solid $border-light;
  box-shadow: 0 -4rpx 16rpx rgba(26, 26, 26, 0.04);
}

// 保存按钮 - 渐变样式（与首页统一）
.save-btn {
  width: 100%;
  height: 96rpx;
  background: $primary-gradient;
  border-radius: $radius-xl;
  border: none;
  color: #fff;
  font-size: $font-size-body;
  font-weight: $font-weight-semibold;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8rpx 24rpx rgba(102, 126, 234, 0.3);
  transition: all $duration-fast $ease-standard;

  &:active {
    transform: scale(0.98);
    box-shadow: 0 4rpx 12rpx rgba(102, 126, 234, 0.2);
  }

  &.btn-disabled {
    opacity: 0.5;
    box-shadow: none;
  }

  &[disabled] {
    cursor: not-allowed;
  }
}

.btn-loading {
  margin-right: $space-xs;
}
</style>