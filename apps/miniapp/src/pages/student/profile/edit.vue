<template>
  <view class="edit-page">
    <!-- 装饰背景 -->
    <view class="page-decoration">
      <view class="deco-text">
        <text class="deco-line1">舞动青春</text>
        <text class="deco-line2">遇见更好的自己</text>
        <text class="deco-heart">♥</text>
      </view>
      <view class="deco-dancer"></view>
    </view>

    <!-- 主内容区域 -->
    <view class="main-content">
      <scroll-view scroll-y class="form-scroll" :show-scrollbar="false">
        <view class="form-card">
          <!-- 头像区域 -->
          <view class="avatar-section">
            <view class="avatar-label-row">
              <AppIcon name="user" :size="36" color="#8b7355" />
              <text class="section-label">头像</text>
            </view>
            <view class="avatar-wrapper" @tap="changeAvatar">
              <view class="avatar">
                <text class="avatar-text">{{
                  form.nickname?.charAt(0) || "?"
                }}</text>
              </view>
              <view class="camera-badge">
                <AppIcon name="camera" :size="24" color="#666" />
              </view>
            </view>
          </view>

          <!-- 姓名输入 -->
          <view class="form-item">
            <view class="label-row">
              <AppIcon name="user" :size="32" color="#8b7355" />
              <text class="label">姓名</text>
              <text class="required-mark">*</text>
            </view>
            <input
              v-model="form.nickname"
              type="text"
              placeholder="请输入姓名"
              class="input-field"
              :class="{ 'input-error': errors.nickname }"
              @blur="validateNickname"
            />
            <text v-if="errors.nickname" class="error-msg">{{
              errors.nickname
            }}</text>
          </view>

          <!-- 手机号（只读） -->
          <view class="form-item">
            <view class="label-row">
              <AppIcon name="phone" :size="32" color="#8b7355" />
              <text class="label">手机号</text>
            </view>
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
            <view class="label-row">
              <AppIcon name="edit" :size="32" color="#8b7355" />
              <text class="label">简介</text>
            </view>
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
        <text>{{ isLoading ? "保存中..." : "保存修改" }}</text>
      </button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { userApi } from "@/api";
import AppIcon from "@/components/AppIcon.vue";
import { computed, onMounted, reactive, ref } from "vue";

const isLoading = ref(false);

const form = reactive({
  nickname: "",
  phone: "",
  bio: "",
});

const errors = reactive({
  nickname: "",
});

const isFormValid = computed(() => {
  return form.nickname.trim();
});

onMounted(() => {
  loadUserInfo();
});

const loadUserInfo = () => {
  const info = uni.getStorageSync("user_info");
  if (info) {
    const user = JSON.parse(info);
    form.nickname = user.nickname || "";
    form.phone = user.phone || "";
    form.bio = user.bio || "";
  }
};

const validateNickname = () => {
  errors.nickname = form.nickname.trim() ? "" : "请输入姓名";
};

const changeAvatar = () => {
  uni.showToast({ title: "头像上传功能开发中", icon: "none" });
};

const handleSubmit = async () => {
  validateNickname();

  if (!isFormValid.value) return;

  isLoading.value = true;
  try {
    const result = await userApi.update({
      nickname: form.nickname,
      bio: form.bio,
    });

    if (result.code === 0 || result.code === 200) {
      const userInfo = JSON.parse(uni.getStorageSync("user_info"));
      userInfo.nickname = form.nickname;
      userInfo.bio = form.bio;
      uni.setStorageSync("user_info", JSON.stringify(userInfo));

      uni.showToast({ title: "保存成功", icon: "success" });
      setTimeout(() => uni.navigateBack(), 1500);
    } else {
      uni.showToast({ title: result.msg || "保存失败", icon: "none" });
    }
  } catch {
    uni.showToast({ title: "保存失败", icon: "none" });
  } finally {
    isLoading.value = false;
  }
};
</script>

<style lang="scss" scoped>
.edit-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #fef6f0 0%, #faf5f0 50%, #f8f2ed 100%);
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

// 装饰背景
.page-decoration {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 300rpx;
  pointer-events: none;
  overflow: hidden;

  .deco-text {
    position: absolute;
    top: 120rpx;
    left: 40rpx;
    display: flex;
    flex-direction: column;
    gap: 8rpx;
    opacity: 0.4;

    .deco-line1 {
      font-size: 32rpx;
      color: #c9a66b;
      font-weight: 500;
      letter-spacing: 2rpx;
      transform: rotate(-5deg);
    }

    .deco-line2 {
      font-size: 26rpx;
      color: #c9a66b;
      font-weight: 400;
      letter-spacing: 1rpx;
      transform: rotate(-3deg);
      margin-left: 20rpx;
    }

    .deco-heart {
      position: absolute;
      top: -10rpx;
      right: -30rpx;
      font-size: 24rpx;
      color: #d9a7b0;
      transform: rotate(15deg);
    }
  }

  .deco-dancer {
    position: absolute;
    top: 0;
    right: -40rpx;
    width: 300rpx;
    height: 300rpx;
    background: radial-gradient(
      ellipse at center,
      rgba(217, 167, 176, 0.15) 0%,
      transparent 70%
    );
    opacity: 0.6;
  }
}

// 主内容区域
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
  position: relative;
  z-index: 1;
}

.form-scroll {
  flex: 1;
  height: 0;
  padding: 24rpx;
  padding-bottom: 200rpx;
}

// 表单卡片
.form-card {
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(20rpx);
  -webkit-backdrop-filter: blur(20rpx);
  border-radius: 24rpx;
  padding: 32rpx;
  box-shadow: 0 4rpx 20rpx rgba(44, 24, 16, 0.06);
  border: 1rpx solid rgba(201, 166, 107, 0.15);
}

// 头像区域
.avatar-section {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 32rpx;
  padding-bottom: 32rpx;
  border-bottom: 1rpx solid rgba(201, 166, 107, 0.15);
}

.avatar-label-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.section-label {
  font-size: 28rpx;
  color: #2c1810;
  font-weight: 500;
}

.avatar-wrapper {
  position: relative;
  width: 140rpx;
  height: 140rpx;
}

.avatar {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: linear-gradient(135deg, #d4a574 0%, #c9a66b 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8rpx 24rpx rgba(201, 166, 107, 0.25);
  border: 4rpx solid rgba(255, 255, 255, 0.9);
}

.avatar-text {
  font-size: 52rpx;
  color: #fff;
  font-weight: 600;
}

.camera-badge {
  position: absolute;
  bottom: 4rpx;
  right: 4rpx;
  width: 44rpx;
  height: 44rpx;
  background: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2rpx 8rpx rgba(44, 24, 16, 0.1);
  border: 2rpx solid rgba(201, 166, 107, 0.2);
}

// 表单项
.form-item {
  margin-bottom: 32rpx;

  &:last-child {
    margin-bottom: 0;
  }
}

.label-row {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-bottom: 12rpx;
}

.label {
  font-size: 28rpx;
  color: #8b7355;
  font-weight: 500;
}

.required-mark {
  font-size: 28rpx;
  color: #e74c3c;
  font-weight: 500;
}

// 输入框
.input-field {
  width: 100%;
  height: 88rpx;
  background: rgba(254, 246, 240, 0.6);
  border: 1rpx solid rgba(201, 166, 107, 0.2);
  border-radius: 16rpx;
  padding: 0 24rpx;
  font-size: 28rpx;
  color: #2c1810;
  transition: all 0.2s ease;

  &:focus {
    border-color: #c9a66b;
    box-shadow: 0 0 0 4rpx rgba(201, 166, 107, 0.1);
    background: rgba(255, 255, 255, 0.8);
  }

  &.input-error {
    border-color: #e74c3c;
    background: rgba(231, 76, 60, 0.05);
  }

  &.input-disabled {
    background: rgba(248, 242, 237, 0.6);
    color: #a89279;
  }
}

.error-msg {
  font-size: 24rpx;
  color: #e74c3c;
  margin-top: 8rpx;
  display: block;
}

// 文本域
.textarea-field {
  width: 100%;
  height: 180rpx;
  background: rgba(254, 246, 240, 0.6);
  border: 1rpx solid rgba(201, 166, 107, 0.2);
  border-radius: 16rpx;
  padding: 24rpx;
  font-size: 28rpx;
  color: #2c1810;
  transition: all 0.2s ease;

  &:focus {
    border-color: #c9a66b;
    box-shadow: 0 0 0 4rpx rgba(201, 166, 107, 0.1);
    background: rgba(255, 255, 255, 0.8);
  }
}

.char-count {
  font-size: 24rpx;
  color: #a89279;
  text-align: right;
  margin-top: 8rpx;
  display: block;
}

// 底部区域
.footer-area {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 24rpx;
  padding-bottom: calc(24rpx + env(safe-area-inset-bottom));
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(20rpx);
  -webkit-backdrop-filter: blur(20rpx);
  border-top: 1rpx solid rgba(201, 166, 107, 0.15);
  box-shadow: 0 -4rpx 16rpx rgba(44, 24, 16, 0.04);
}

// 保存按钮
.save-btn {
  width: 100%;
  height: 96rpx;
  background: linear-gradient(135deg, #d4a574 0%, #c9a66b 100%);
  border-radius: 48rpx;
  border: none;
  color: #fff;
  font-size: 32rpx;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8rpx 24rpx rgba(201, 166, 107, 0.3);
  transition: all 0.2s ease;

  &:active {
    transform: scale(0.98);
    box-shadow: 0 4rpx 12rpx rgba(201, 166, 107, 0.2);
  }

  &.btn-disabled {
    opacity: 0.5;
    box-shadow: none;
  }

  &[disabled] {
    cursor: not-allowed;
  }
}
</style>
