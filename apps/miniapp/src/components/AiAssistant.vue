<template>
  <view class="ai-assistant">
    <!-- 悬浮按钮 -->
    <view
      v-if="isLoggedIn"
      class="ai-fab"
      :class="{ 'ai-fab-active': isVisible }"
      @tap="toggleChat"
    >
      <view class="ai-fab-glow" />
      <view class="ai-fab-circle">
        <AppIcon name="ai-robot" :size="56" color="#fff" />
      </view>
      <view v-if="unreadCount > 0" class="ai-badge">
        {{ unreadCount > 99 ? "99+" : unreadCount }}
      </view>
      <view class="ai-label">AI助手</view>
    </view>

    <!-- 聊天窗口 -->
    <view v-if="isVisible" class="ai-chat-window">
      <!-- 头部 -->
      <view class="chat-header">
        <view class="chat-title-wrapper">
          <view class="header-icon-wrapper">
            <AppIcon name="ai-robot" :size="48" color="#fff" />
          </view>
          <view class="header-text">
            <text class="chat-title">AI 助手</text>
            <text class="chat-subtitle">智能课程助手</text>
          </view>
        </view>
        <view class="chat-actions">
          <view class="action-btn-wrapper" @tap.stop="handleClear">
            <AppIcon name="trash" :size="32" color="rgba(255,255,255,0.9)" />
            <text class="action-btn">清空</text>
          </view>
        </view>
      </view>

      <!-- 聊天面板（共享组件：消息流 + 快捷问题 + 输入区） -->
      <AiChatPanel
        ref="chatPanelRef"
        :session-id="sessionId"
        theme="violet"
        class="ai-chat-panel-fill"
        @message-sent="onMessageSent"
      />
    </view>
  </view>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import AiChatPanel from "./AiChatPanel.vue";
import AppIcon from "./AppIcon.vue";

const props = withDefaults(
  defineProps<{
    sessionId?: string;
  }>(),
  {
    sessionId: "",
  },
);

const emit = defineEmits<{
  (e: "booking-created", data: any): void;
  (e: "booking-cancelled", bookingId: number): void;
  (e: "message-sent", payload: {
    userMessage: string;
    aiResponse: string;
  }): void;
}>();

const isLoggedIn = ref(false);
const isVisible = ref(false);
const unreadCount = ref(0);
const chatPanelRef = ref<InstanceType<typeof AiChatPanel> | null>(null);

const checkLogin = () => {
  const token = uni.getStorageSync("token");
  isLoggedIn.value = !!token;
};

onMounted(() => {
  checkLogin();
  uni.$on("login-success", checkLogin);
});

onBeforeUnmount(() => {
  uni.$off("login-success", checkLogin);
});

const toggleChat = () => {
  isVisible.value = !isVisible.value;
  if (isVisible.value) {
    unreadCount.value = 0;
  }
};

const handleClear = () => {
  chatPanelRef.value?.clearHistory();
};

const onMessageSent = (payload: { userMessage: string; aiResponse: string }) => {
  emit("message-sent", payload);
};

defineExpose({
  toggleChat,
  sendMessage: (...args: unknown[]) =>
    (chatPanelRef.value?.sendMessage as any)?.(...args),
});
</script>

<style lang="scss" scoped>
.ai-assistant {
  position: fixed;
  z-index: 9999;
  right: 30rpx;
  bottom: 200rpx;
}

.ai-fab {
  position: relative;
  width: 120rpx;
  height: 120rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;

  &-glow {
    position: absolute;
    width: 100rpx;
    height: 100rpx;
    border-radius: 50%;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    box-shadow: 0 8rpx 32rpx rgba(102, 126, 234, 0.5);
    animation: pulse-glow 2s ease-in-out infinite;
  }

  &-circle {
    position: relative;
    width: 100rpx;
    height: 100rpx;
    border-radius: 50%;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1;
    box-shadow: 0 8rpx 32rpx rgba(102, 126, 234, 0.4);
  }

  &-active {
    .ai-fab-glow {
      animation: none;
      opacity: 0.6;
    }

    .ai-fab-circle {
      box-shadow: 0 4rpx 16rpx rgba(102, 126, 234, 0.3);
    }
  }

  .ai-badge {
    position: absolute;
    top: 0;
    right: 0;
    background: #ff4757;
    color: white;
    font-size: 20rpx;
    padding: 4rpx 10rpx;
    border-radius: 20rpx;
    min-width: 32rpx;
    text-align: center;
    z-index: 2;
  }

  .ai-label {
    position: absolute;
    top: -8rpx;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    font-size: 20rpx;
    padding: 4rpx 16rpx;
    border-radius: 20rpx;
    white-space: nowrap;
    z-index: 2;
  }
}

@keyframes pulse-glow {
  0%,
  100% {
    transform: scale(1);
    box-shadow: 0 8rpx 32rpx rgba(102, 126, 234, 0.5);
  }
  50% {
    transform: scale(1.05);
    box-shadow: 0 12rpx 40rpx rgba(102, 126, 234, 0.6);
  }
}

.ai-chat-window {
  position: fixed;
  right: 20rpx;
  bottom: 340rpx;
  width: 650rpx;
  height: 800rpx;
  background: #f8f9fc;
  border-radius: 24rpx;
  box-shadow: 0 16rpx 48rpx rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.ai-chat-panel-fill {
  flex: 1;
  min-height: 0;
}

.chat-header {
  padding: 28rpx 32rpx;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  justify-content: space-between;
  align-items: center;

  .chat-title-wrapper {
    display: flex;
    align-items: center;
    gap: 16rpx;
  }

  .header-icon-wrapper {
    width: 64rpx;
    height: 64rpx;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.2);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .header-text {
    display: flex;
    flex-direction: column;
    gap: 4rpx;
  }

  .chat-title {
    font-size: 32rpx;
    font-weight: 600;
    color: white;
  }

  .chat-subtitle {
    font-size: 22rpx;
    color: rgba(255, 255, 255, 0.8);
  }

  .chat-actions {
    .action-btn-wrapper {
      display: flex;
      align-items: center;
      gap: 8rpx;
      padding: 8rpx 16rpx;
      border-radius: 20rpx;
      background: rgba(255, 255, 255, 0.15);

      &:active {
        background: rgba(255, 255, 255, 0.25);
      }
    }

    .action-btn {
      font-size: 24rpx;
      color: rgba(255, 255, 255, 0.9);
    }
  }
}
</style>
