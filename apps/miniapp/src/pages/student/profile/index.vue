<template>
  <view class="profile-container">
    <!-- 自定义导航栏 -->
    <AppNavbar title="" :show-back="false" variant="default">
      <template #left>
        <view class="navbar-title">我的</view>
      </template>
    </AppNavbar>

    <!-- 个人信息区 -->
    <view class="profile-header">
      <view class="header-bg-decoration"></view>
      <view class="profile-content">
        <view class="avatar-section">
          <view v-if="!userInfo?.avatar" class="avatar-placeholder">
            <text class="avatar-text">{{ getUserInitial() }}</text>
          </view>
          <image
            v-else
            class="avatar"
            :src="userInfo.avatar"
            mode="aspectFill"
          />
        </view>
        <view class="user-info-section">
          <text class="user-name">{{ userInfo?.nickname || "学员" }}</text>
          <view class="user-role-row">
            <text class="user-role">学员</text>
            <text class="role-divider">·</text>
            <text class="membership-level">{{ getMembershipLevel() }}</text>
          </view>
          <view class="membership-badge">
            <AppIcon name="crown" :size="28" color="#c9a66b" />
            <text class="badge-text">{{ getMembershipLevel() }}</text>
          </view>
        </view>
        <!-- <view class="edit-btn" @tap="goToEdit">
          <AppIcon name="edit" :size="28" color="#8b7355" />
          <text class="edit-text">编辑</text>
        </view> -->
      </view>
    </view>

    <!-- 内容区域 -->
    <view class="content-area">
      <!-- 我的会员卡 - 突出卡片 -->
      <view class="membership-card" @tap="goToMembership">
        <view class="card-bg-pattern"></view>
        <view class="card-content">
          <view class="card-left">
            <view class="card-icon-wrapper">
              <AppIcon name="crown" :size="48" color="#c9a66b" />
            </view>
            <view class="card-info">
              <text class="card-title">我的会员卡</text>
              <text class="card-desc">查看会员权益 · 课程信息 · 剩余课时</text>
            </view>
          </view>
          <AppIcon name="arrow-right" :size="36" color="#c9a66b" />
        </view>
      </view>

      <!-- 功能菜单组 -->
      <view class="menu-group">
        <!-- 预约记录 -->
        <view class="menu-card" @tap="goToBookings">
          <view class="menu-item">
            <view class="menu-left">
              <view class="menu-icon-wrapper">
                <AppIcon name="calendar" :size="36" color="#8b7355" />
              </view>
              <view class="menu-info">
                <text class="menu-title">预约记录</text>
                <text class="menu-desc">查看我的课程预约与历史记录</text>
              </view>
            </view>
            <AppIcon name="arrow-right" :size="32" color="#c9a66b" />
          </view>
        </view>
      </view>

      <!-- 账号设置组 -->
      <view class="menu-group">
        <!-- 解绑微信 -->
        <view class="menu-card" @tap="handleUnbindWechat">
          <view class="menu-item">
            <view class="menu-left">
              <view class="menu-icon-wrapper">
                <AppIcon name="wechat" :size="36" color="#8b7355" />
              </view>
              <view class="menu-info">
                <text class="menu-title">解绑微信</text>
                <text class="menu-desc">已绑定微信账号</text>
              </view>
            </view>
            <AppIcon name="arrow-right" :size="32" color="#c9a66b" />
          </view>
        </view>

        <!-- 退出登录 -->
        <view class="menu-card" @tap="handleLogout">
          <view class="menu-item">
            <view class="menu-left">
              <view class="menu-icon-wrapper logout-icon">
                <AppIcon name="logout" :size="36" color="#e74c3c" />
              </view>
              <view class="menu-info">
                <text class="menu-title">退出登录</text>
                <text class="menu-desc">安全退出当前账号</text>
              </view>
            </view>
            <AppIcon name="arrow-right" :size="32" color="#c9a66b" />
          </view>
        </view>
      </view>
    </view>

    <StudentTabBar currentRoute="/pages/student/profile/index" />

    <!-- AI 智能助手 -->
    <AiAssistant :session-id="'student_' + (userId || 'default')" />
  </view>
</template>

<script setup lang="ts">
import { clearAuthData } from "@/api";
import AiAssistant from "@/components/AiAssistant.vue";
import AppIcon from "@/components/AppIcon.vue";
import AppNavbar from "@/components/AppNavbar.vue";
import StudentTabBar from "@/components/StudentTabBar.vue";
import { checkLogin, logout } from "@/utils/auth";
import { navigateTo } from "@/utils/navigation";
import { wechatUnbind } from "@/utils/wechat";
import { onMounted, onUnmounted, ref } from "vue";

const userInfo = ref<any>(null);
const userId = ref("");

let isUnmounted = false;

onMounted(() => {
  console.log('\n ===== 学员"我的"页面 - onMounted 触发 =====\n');

  if (!checkLogin("student")) return;

  loadUserInfo();
});

onUnmounted(() => {
  isUnmounted = true;
});

const loadUserInfo = () => {
  const info = uni.getStorageSync("user_info");
  if (info) {
    const parsed = JSON.parse(info);
    userInfo.value = parsed;
    userId.value = parsed.id || "";
    console.log("✅ 用户信息已加载:", parsed?.nickname || "未知");
  }
};

const getMembershipLevel = () => {
  return userInfo.value?.membership_level || "普通会员";
};

const getUserInitial = () => {
  const nickname = userInfo.value?.nickname || "学员";
  return nickname.charAt(0).toUpperCase();
};

const handleLogout = () => {
  uni.showModal({
    title: "确认退出",
    content: "确定要退出登录吗？",
    success: (res) => {
      if (res.confirm) {
        logout();
      }
    },
  });
};

const goToEdit = () => {
  navigateTo({ url: "/pages/student/profile/edit" });
};

const goToMembership = () => {
  navigateTo({ url: "/pages/student/membership/index" });
};

const goToBookings = () => {
  navigateTo({ url: "/pages/student/bookings/index" });
};

const handleUnbindWechat = () => {
  uni.showModal({
    title: "解绑微信",
    content: "解绑后您将退出当前登录状态，需重新通过手机号登录。确定要解绑吗？",
    confirmText: "确定解绑",
    cancelText: "取消",
    confirmColor: "#e74c3c",
    success: async (res) => {
      if (res.confirm) {
        uni.showLoading({ title: "解绑中...", mask: true });
        const result = await wechatUnbind();
        uni.hideLoading();
        if (result.success) {
          console.log("🔓 微信解绑成功，开始清除本地登录态...");

          uni.setStorageSync("just_unbound_wechat", "true");
          console.log("✅ 已设置 just_unbound_wechat 标志");

          clearAuthData();

          console.log("✅ 本地存储已清除，当前状态:");
          console.log("  - token:", uni.getStorageSync("token") || "(空)");
          console.log(
            "  - refresh_token:",
            uni.getStorageSync("refresh_token") || "(空)",
          );
          console.log(
            "  - user_role:",
            uni.getStorageSync("user_role") || "(空)",
          );
          console.log(
            "  - tenant_slug:",
            uni.getStorageSync("tenant_slug") || "(空)",
          );
          console.log(
            "  - just_unbound_wechat:",
            uni.getStorageSync("just_unbound_wechat") || "(空)",
          );

          uni.showToast({
            title: "微信已解绑",
            icon: "success",
            duration: 1500,
          });
          setTimeout(() => {
            console.log(" 准备跳转到首页...");
            uni.reLaunch({
              url: "/pages/index/index",
              complete: () => {
                console.log("✅ 跳转完成");
              },
              fail: (err: any) => {
                console.error(" 跳转失败:", err);
              },
            });
          }, 1500);
        } else {
          uni.showToast({ title: result.msg, icon: "none" });
        }
      }
    },
  });
};
</script>

<style lang="scss">
.profile-container {
  min-height: 100vh;
  background: linear-gradient(180deg, #fef6f0 0%, #faf5f0 50%, #f8f2ed 100%);
  padding-bottom: 140rpx;
}

// 导航栏标题
.navbar-title {
  font-size: 36rpx;
  font-weight: 600;
  color: #2c1810;
  letter-spacing: 1rpx;
}

// 个人信息区
.profile-header {
  position: relative;
  padding: 40rpx 32rpx 60rpx;
  overflow: hidden;

  .header-bg-decoration {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background:
      radial-gradient(
        ellipse at 80% 20%,
        rgba(212, 165, 116, 0.15) 0%,
        transparent 50%
      ),
      radial-gradient(
        ellipse at 20% 80%,
        rgba(217, 167, 176, 0.12) 0%,
        transparent 50%
      );
    pointer-events: none;
  }

  .profile-content {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    gap: 24rpx;
  }

  .avatar-section {
    flex-shrink: 0;

    .avatar {
      width: 140rpx;
      height: 140rpx;
      border-radius: 50%;
      border: 4rpx solid rgba(255, 255, 255, 0.9);
      box-shadow: 0 8rpx 24rpx rgba(44, 24, 16, 0.12);
      background: #fff;
    }

    .avatar-placeholder {
      width: 140rpx;
      height: 140rpx;
      border-radius: 50%;
      border: 4rpx solid rgba(255, 255, 255, 0.9);
      box-shadow: 0 8rpx 24rpx rgba(44, 24, 16, 0.12);
      background: linear-gradient(135deg, #c9a66b 0%, #d9a7b0 100%);
      display: flex;
      align-items: center;
      justify-content: center;

      .avatar-text {
        font-size: 56rpx;
        font-weight: 600;
        color: #fff;
        text-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.1);
      }
    }
  }

  .user-info-section {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 8rpx;

    .user-name {
      font-size: 36rpx;
      font-weight: 600;
      color: #2c1810;
      letter-spacing: 0.5rpx;
    }

    .user-role-row {
      display: flex;
      align-items: center;
      gap: 8rpx;

      .user-role {
        font-size: 26rpx;
        color: #8b7355;
        font-weight: 500;
      }

      .role-divider {
        font-size: 26rpx;
        color: #c9a66b;
        opacity: 0.6;
      }

      .membership-level {
        font-size: 26rpx;
        color: #c9a66b;
        font-weight: 500;
      }
    }

    .membership-badge {
      display: inline-flex;
      align-items: center;
      gap: 8rpx;
      padding: 6rpx 16rpx;
      background: linear-gradient(
        135deg,
        rgba(201, 166, 107, 0.15) 0%,
        rgba(217, 167, 176, 0.12) 100%
      );
      border-radius: 24rpx;
      width: fit-content;
      margin-top: 4rpx;

      .badge-text {
        font-size: 22rpx;
        color: #c9a66b;
        font-weight: 500;
      }
    }
  }

  .edit-btn {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: 8rpx;
    padding: 14rpx 28rpx;
    background: rgba(255, 255, 255, 0.85);
    backdrop-filter: blur(10rpx);
    border: 1rpx solid rgba(201, 166, 107, 0.2);
    border-radius: 40rpx;
    box-shadow: 0 4rpx 12rpx rgba(44, 24, 16, 0.06);
    transition: all 0.2s ease;

    &:active {
      transform: scale(0.96);
      background: rgba(255, 255, 255, 0.95);
    }

    .edit-text {
      font-size: 26rpx;
      color: #8b7355;
      font-weight: 500;
    }
  }
}

// 内容区域
.content-area {
  padding: 0 24rpx;
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}

// 会员卡突出卡片
.membership-card {
  position: relative;
  background: linear-gradient(135deg, #fef6f0 0%, #faf0e6 100%);
  border-radius: 24rpx;
  overflow: hidden;
  box-shadow: 0 4rpx 20rpx rgba(201, 166, 107, 0.15);
  border: 1rpx solid rgba(201, 166, 107, 0.2);
  transition: all 0.2s ease;

  &:active {
    transform: scale(0.98);
    box-shadow: 0 2rpx 12rpx rgba(201, 166, 107, 0.2);
  }

  .card-bg-pattern {
    position: absolute;
    top: 0;
    right: 0;
    width: 200rpx;
    height: 200rpx;
    background: radial-gradient(
      circle,
      rgba(201, 166, 107, 0.08) 0%,
      transparent 70%
    );
    pointer-events: none;
  }

  .card-content {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 32rpx;

    .card-left {
      display: flex;
      align-items: center;
      gap: 20rpx;
      flex: 1;

      .card-icon-wrapper {
        width: 88rpx;
        height: 88rpx;
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(
          135deg,
          rgba(201, 166, 107, 0.2) 0%,
          rgba(217, 167, 176, 0.15) 100%
        );
        border-radius: 50%;
        flex-shrink: 0;
      }

      .card-info {
        display: flex;
        flex-direction: column;
        gap: 8rpx;

        .card-title {
          font-size: 32rpx;
          font-weight: 600;
          color: #2c1810;
          letter-spacing: 0.5rpx;
        }

        .card-desc {
          font-size: 24rpx;
          color: #8b7355;
          line-height: 1.4;
        }
      }
    }
  }
}

// 菜单组
.menu-group {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

// 菜单卡片
.menu-card {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(10rpx);
  border-radius: 20rpx;
  overflow: hidden;
  border: 1rpx solid rgba(201, 166, 107, 0.1);
  box-shadow: 0 2rpx 12rpx rgba(44, 24, 16, 0.04);
  transition: all 0.2s ease;

  &:active {
    transform: scale(0.98);
    background: rgba(255, 255, 255, 0.95);
  }

  .menu-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 28rpx 24rpx;

    .menu-left {
      display: flex;
      align-items: center;
      gap: 20rpx;
      flex: 1;

      .menu-icon-wrapper {
        width: 72rpx;
        height: 72rpx;
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(
          135deg,
          rgba(254, 246, 240, 0.8) 0%,
          rgba(250, 240, 230, 0.6) 100%
        );
        border-radius: 50%;
        flex-shrink: 0;

        &.logout-icon {
          background: linear-gradient(
            135deg,
            rgba(231, 76, 60, 0.1) 0%,
            rgba(231, 76, 60, 0.05) 100%
          );
        }
      }

      .menu-info {
        display: flex;
        flex-direction: column;
        gap: 6rpx;
        flex: 1;

        .menu-title {
          font-size: 30rpx;
          font-weight: 500;
          color: #2c1810;
          letter-spacing: 0.3rpx;
        }

        .menu-desc {
          font-size: 24rpx;
          color: #a89279;
          line-height: 1.3;
        }
      }
    }
  }
}
</style>
