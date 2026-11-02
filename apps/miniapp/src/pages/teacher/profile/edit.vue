<template>
  <view class="container">
    <view class="header">
      <view class="back-btn" @tap="goBack">
        <text class="back-icon">←</text>
      </view>
      <text class="header-title">编辑资料</text>
      <view class="placeholder"></view>
    </view>

    <scroll-view scroll-y class="form-scroll" :show-scrollbar="false">
      <view class="form-area">
        <view class="form-item avatar-item">
          <text class="label">头像</text>
          <view class="avatar-wrapper" @tap="changeAvatar">
            <image
              v-if="avatarPreviewUrl"
              class="avatar-image"
              :src="avatarPreviewUrl"
              mode="aspectFill"
              @error="handleAvatarImageError"
            />
            <view v-else class="avatar">
              <text class="avatar-icon">👤</text>
            </view>
            <view class="camera-icon">
              <text>📷</text>
            </view>
          </view>
        </view>

        <view class="form-item">
          <text class="label">姓名 *</text>
          <input
            v-model="form.nickname"
            type="text"
            placeholder="请输入姓名"
            class="input"
            @blur="validateNickname"
          />
          <text v-if="errors.nickname" class="error-text">{{ errors.nickname }}</text>
        </view>

        <view class="form-item">
          <text class="label">手机号</text>
          <input
            v-model="form.phone"
            type="number"
            class="input"
            disabled
            placeholder="手机号"
          />
        </view>

        <view class="form-item">
          <text class="label">简介</text>
          <textarea
            v-model="form.bio"
            placeholder="介绍一下自己..."
            class="textarea"
            :maxlength="200"
          />
          <text class="text-count">{{ form.bio?.length || 0 }}/200</text>
        </view>
      </view>
    </scroll-view>

    <view class="footer">
      <button
        class="submit-btn"
        :class="{ disabled: !isFormValid }"
        :disabled="!isFormValid || isLoading"
        @tap="handleSubmit"
      >
        <text v-if="isLoading" class="loading">⏳</text>
        <text>{{ isLoading ? '保存中...' : '保存修改' }}</text>
      </button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { teacherApi, uploadApi } from '@/api'

const isLoading = ref(false)

const form = reactive({
  nickname: '',
  phone: '',
  bio: '',
  avatar: ''
})

// 头像预览 URL（业务字段 avatar 只存 object_key）
const avatarPreviewUrl = ref('')
const avatarObjectKey = ref('')

const errors = reactive({
  nickname: ''
})

const isFormValid = computed(() => {
  return form.nickname.trim()
})

onMounted(() => {
  loadUserInfo()
})

const loadUserInfo = async () => {
  const info = uni.getStorageSync('user_info')
  if (info) {
    const user = JSON.parse(info)
    form.nickname = user.nickname || ''
    form.phone = user.phone || ''
    form.bio = user.bio || ''
    avatarPreviewUrl.value = user.avatar || ''
  }
  // 头像/简介以后端为准（私有桶下预签名 URL 每次重新签发）
  try {
    const res = await teacherApi.getInfo()
    const data: any = res.data || {}
    form.nickname = data.nickname || form.nickname
    form.bio = data.intro ?? form.bio
    avatarPreviewUrl.value = data.avatar || ''
  } catch {
    // 忽略：回退到本地缓存
  }
}

const validateNickname = () => {
  errors.nickname = form.nickname.trim() ? '' : '请输入姓名'
}

const changeAvatar = async () => {
  let chooseResult: UniApp.ChooseImageSuccessCallbackResult
  try {
    chooseResult = await uni.chooseImage({
      count: 1,
      sizeType: ['compressed'],
      sourceType: ['album', 'camera']
    })
  } catch {
    return
  }

  const tempFile = (chooseResult.tempFiles as any)?.[0]
  const filePath = chooseResult.tempFilePaths?.[0]
  if (!filePath) return
  if (tempFile && tempFile.size / 1024 / 1024 >= 2) {
    uni.showToast({ title: '头像大小不能超过 2MB', icon: 'none' })
    return
  }

  uni.showLoading({ title: '上传中...', mask: true })
  try {
    const result = await uploadApi.uploadImage(filePath, 'avatar')
    avatarObjectKey.value = result.data.object_key
    avatarPreviewUrl.value = result.data.url
    form.avatar = result.data.object_key
    uni.showToast({ title: '头像已上传，保存后生效', icon: 'none' })
  } catch (e: any) {
    uni.showToast({ title: e?.message || '头像上传失败', icon: 'none' })
  } finally {
    uni.hideLoading()
  }
}

// 预签名地址过期导致图片加载失败时，按 object_key 换新链接
const handleAvatarImageError = async () => {
  if (!avatarObjectKey.value) return
  try {
    const res = await uploadApi.getUrl(avatarObjectKey.value)
    avatarPreviewUrl.value = res.data?.url || ''
  } catch {
    // 忽略：保持占位
  }
}

const handleSubmit = async () => {
  validateNickname()

  if (!isFormValid.value) return

  isLoading.value = true
  try {
    const result = await teacherApi.updateInfo({
      nickname: form.nickname,
      intro: form.bio,
      ...(form.avatar ? { avatar: form.avatar } : {})
    })

    if (result.code === 0 || result.code === 200) {
      const data: any = result.data || {}
      const userInfo = JSON.parse(uni.getStorageSync('user_info') || '{}')
      userInfo.nickname = data.nickname ?? form.nickname
      userInfo.bio = data.intro ?? form.bio
      userInfo.avatar = data.avatar ?? avatarPreviewUrl.value
      uni.setStorageSync('user_info', JSON.stringify(userInfo))

      uni.showToast({ title: '保存成功', icon: 'success' })
      setTimeout(() => uni.navigateBack(), 1500)
    } else {
      uni.showToast({ title: result.msg || '保存失败', icon: 'none' })
    }
  } catch (e: any) {
    uni.showToast({ title: e?.message || '保存失败', icon: 'none' })
  } finally {
    isLoading.value = false
  }
}

const goBack = () => {
  uni.navigateBack()
}
</script>

<style lang="scss">
/* ✅ 已通过 vite.config.ts 全局注入 scrollbar 样式 */
.container {
  height: 100vh;             // ✅ 使用固定高度
  background: #f5f5f5;
  display: flex;
  flex-direction: column;
  overflow: hidden;          // ✅ 防止外层滚动
}

.header {
  flex-shrink: 0;            // ✅ 头部不被压缩
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 60rpx 32rpx 24rpx;
  background: #fff;
}

.back-btn {
  width: 64rpx;
  height: 64rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.back-icon {
  font-size: 40rpx;
}

.header-title {
  font-size: 34rpx;
  font-weight: bold;
}

.placeholder {
  width: 64rpx;
}

.form-scroll {
  flex: 1;                   // ✅ 现在能正确计算高度
  height: 0;                 // ✅ 关键：让 flex:1 正确计算
  padding: 24rpx;
  padding-bottom: 120rpx;    // ✅ 底部留白（保存按钮区域）
  box-sizing: border-box;
}

.form-area {
  background: #fff;
  border-radius: 16rpx;
  padding: 32rpx;
}

.form-item {
  margin-bottom: 28rpx;
}

.label {
  font-size: 28rpx;
  color: #333;
  margin-bottom: 16rpx;
  display: block;
}

.input {
  width: 100%;
  height: 88rpx;
  background: #f8f8f8;
  border-radius: 12rpx;
  padding: 0 24rpx;
  font-size: 28rpx;

  &[disabled] {
    color: #999;
  }
}

.error-text {
  font-size: 24rpx;
  color: #ff4d4f;
  margin-top: 12rpx;
  display: block;
}

.avatar-item {
  margin-bottom: 32rpx;
}

.avatar-wrapper {
  position: relative;
  width: 160rpx;
  height: 160rpx;
}

.avatar {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-image {
  width: 100%;
  height: 100%;
  border-radius: 50%;
}

.avatar-text,
.avatar-icon {
  font-size: 56rpx;
  color: #fff;
  font-weight: bold;
}

.camera-icon {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 48rpx;
  height: 48rpx;
  background: #667eea;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.camera-icon text {
  font-size: 24rpx;
}

.textarea {
  width: 100%;
  height: 160rpx;
  background: #f8f8f8;
  border-radius: 12rpx;
  padding: 20rpx 24rpx;
  font-size: 28rpx;
}

.text-count {
  font-size: 24rpx;
  color: #999;
  text-align: right;
  margin-top: 12rpx;
  display: block;
}

.footer {
  padding: 24rpx 32rpx 48rpx;
  background: #fff;
  border-top: 1rpx solid #f0f0f0;
}

.submit-btn {
  width: 100%;
  height: 96rpx;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 16rpx;
  border: none;
  color: #fff;
  font-size: 32rpx;
  font-weight: bold;
  display: flex;
  align-items: center;
  justify-content: center;

  &.disabled {
    opacity: 0.5;
  }
}

.loading {
  margin-right: 12rpx;
}
</style>