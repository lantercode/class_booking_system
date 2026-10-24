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
          <view class="action-btn-wrapper" @tap.stop="clearHistory">
            <AppIcon name="trash" :size="32" color="rgba(255,255,255,0.9)" />
            <text class="action-btn">清空</text>
          </view>
        </view>
      </view>

      <!-- 消息列表 -->
      <scroll-view
        class="chat-messages"
        scroll-y
        :scroll-into-view="scrollToView"
        :scroll-top="scrollTop"
      >
        <!-- 欢迎区域 -->
        <view
          v-if="messages.length === 0 && !isLoading"
          class="welcome-section"
        >
          <view class="welcome-badge">
            <AppIcon name="lightbulb" :size="40" color="#667eea" />
            <text class="welcome-text">您可以问我：</text>
          </view>

          <!-- 快捷功能卡片 -->
          <view
            v-for="(item, idx) in quickActions"
            :key="idx"
            class="quick-action-card"
            @tap="sendQuickMessage(item.text)"
          >
            <view class="card-icon-wrapper">
              <AppIcon :name="item.icon" :size="48" color="#667eea" />
            </view>
            <view class="card-content">
              <text class="card-title">{{ item.label }}</text>
              <text class="card-desc">{{ item.description }}</text>
            </view>
            <view class="card-arrow">
              <AppIcon name="arrow-right" :size="32" color="#c0c0c0" />
            </view>
          </view>
        </view>

        <!-- 消息列表 -->
        <view
          v-for="(msg, index) in messages"
          :id="'msg-' + index"
          :key="index"
          class="message-wrapper"
          :class="msg.role"
        >
          <view class="message-avatar" v-if="msg.role === 'assistant'">
            <view class="avatar-circle">
              <AppIcon name="ai-robot" :size="32" color="#fff" />
            </view>
          </view>
          <view class="message-bubble">
            <text class="message-text">{{ msg.content }}</text>
          </view>
        </view>

        <!-- 加载中 -->
        <view v-if="isLoading" class="message-wrapper assistant">
          <view class="message-avatar">
            <view class="avatar-circle">
              <AppIcon name="ai-robot" :size="32" color="#fff" />
            </view>
          </view>
          <view class="message-bubble loading">
            <view class="loading-dots">
              <view class="dot"></view>
              <view class="dot"></view>
              <view class="dot"></view>
            </view>
          </view>
        </view>
      </scroll-view>

      <!-- 输入框 -->
      <view class="chat-input-area">
        <view class="input-wrapper">
          <view class="input-icon">
            <AppIcon name="message" :size="36" color="#999" />
          </view>
          <input
            class="chat-input"
            v-model="inputText"
            placeholder="输入您的问题..."
            :focus="isInputFocused"
            confirm-type="send"
            @confirm="sendMessage"
            @focus="isInputFocused = true"
            @blur="isInputFocused = false"
          />
        </view>
        <view
          class="send-btn"
          :class="{ 'send-btn-active': inputText.trim() }"
          @tap="sendMessage"
        >
          <AppIcon
            name="send"
            :size="36"
            :color="inputText.trim() ? '#fff' : '#999'"
          />
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { aiChatApi } from "@/api";
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import AppIcon from "./AppIcon.vue";

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

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
const messages = ref<Message[]>([]);
const inputText = ref("");
const isLoading = ref(false);
const isInputFocused = ref(false);
const unreadCount = ref(0);
const scrollToView = ref("");
const scrollTop = ref(0);

const quickActions = [
  {
    label: "查询课程",
    text: "帮我查一下有哪些课程",
    description: "查看课程信息、课程安排、上课时间等",
    icon: "book",
  },
  {
    label: "预约课程",
    text: "帮我约一节瑜伽课",
    description: "预约课程、选择时间、查看可用时段",
    icon: "calendar",
  },
  {
    label: "查询余额",
    text: "我的课时余额还剩多少",
    description: "查看账户余额、消费记录、充值信息",
    icon: "wallet",
  },
  {
    label: "我的预约",
    text: "查看我的预约记录",
    description: "查看我的预约、课程详情、预约状态",
    icon: "clipboard",
  },
];

const buildSessionId = (): string => {
  if (props.sessionId) return props.sessionId;

  const userInfo = uni.getStorageSync("userInfo");
  const userId = userInfo?.id || userInfo?.user_id || "anon";
  return `session_${userId}`;
};

let currentSessionId = buildSessionId();

const checkLogin = () => {
  const token = uni.getStorageSync("token");
  const wasLoggedIn = isLoggedIn.value;
  isLoggedIn.value = !!token;

  if (isLoggedIn.value && isLoggedIn.value !== wasLoggedIn) {
    currentSessionId = buildSessionId();
    messages.value = [];
  }
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
    loadHistory();
  }
};

const loadHistory = async () => {
  try {
    const res = await aiChatApi.getHistory(currentSessionId);
    if (res.code === 0 || res.code === 200) {
      messages.value = (res.data || []).map((msg) => ({
        role: msg.role,
        content: msg.content,
        timestamp: Date.now(),
      }));
      scrollToBottom();
    }
  } catch (error) {
    console.error("加载历史记录失败:", error);
  }
};

const sendMessage = async () => {
  const text = inputText.value.trim();
  if (!text || isLoading.value) return;

  inputText.value = "";

  messages.value.push({
    role: "user",
    content: text,
    timestamp: Date.now(),
  });

  isLoading.value = true;
  scrollToBottom();

  try {
    const res = await aiChatApi.chat(text, currentSessionId);

    if (res.code === 0 || res.code === 200) {
      const aiResponse =
        res.data?.response || res.msg || "抱歉，我暂时无法回答";

      messages.value.push({
        role: "assistant",
        content: aiResponse,
        timestamp: Date.now(),
      });

      emit("message-sent", { userMessage: text, aiResponse });
    } else {
      messages.value.push({
        role: "assistant",
        content: res.msg || "请求失败，请稍后重试",
        timestamp: Date.now(),
      });
    }
  } catch (error: any) {
    console.error("AI 对话失败:", error);
    messages.value.push({
      role: "assistant",
      content: "网络错误，请检查连接后重试",
      timestamp: Date.now(),
    });
  } finally {
    isLoading.value = false;
    scrollToBottom();
  }
};

const sendQuickMessage = (text: string) => {
  inputText.value = text;
  sendMessage();
};

const clearHistory = async () => {
  uni.showModal({
    title: "提示",
    content: "确定要清空聊天记录吗？",
    success: async (res) => {
      if (res.confirm) {
        try {
          await aiChatApi.clearHistory(currentSessionId);
          messages.value = [];
          uni.showToast({ title: "已清空", icon: "success" });
        } catch (error) {
          uni.showToast({ title: "清空失败", icon: "none" });
        }
      }
    },
  });
};

const scrollToBottom = () => {
  nextTick(() => {
    if (messages.value.length > 0) {
      scrollToView.value = `msg-${messages.value.length - 1}`;
      scrollTop.value = Math.random() * 100;
    }
  });
};

defineExpose({
  toggleChat,
  sendMessage,
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

.chat-messages {
  flex: 1;
  padding: 24rpx;
  background: #f8f9fc;
  overflow-y: auto;

  .welcome-section {
    padding: 20rpx 0;

    .welcome-badge {
      display: inline-flex;
      align-items: center;
      gap: 12rpx;
      background: rgba(102, 126, 234, 0.08);
      padding: 16rpx 28rpx;
      border-radius: 40rpx;
      margin: 0 auto 32rpx;
      width: fit-content;

      .welcome-text {
        font-size: 28rpx;
        font-weight: 600;
        color: #333;
      }
    }
  }

  .quick-action-card {
    display: flex;
    align-items: center;
    background: white;
    padding: 24rpx;
    margin-bottom: 20rpx;
    border-radius: 20rpx;
    box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.06);
    transition: all 0.2s ease;

    &:active {
      transform: scale(0.98);
      box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.08);
    }

    .card-icon-wrapper {
      width: 80rpx;
      height: 80rpx;
      border-radius: 20rpx;
      background: #f0f0ff;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      margin-right: 20rpx;
    }

    .card-content {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 8rpx;

      .card-title {
        font-size: 30rpx;
        font-weight: 600;
        color: #333;
      }

      .card-desc {
        font-size: 24rpx;
        color: #999;
        line-height: 1.4;
      }
    }

    .card-arrow {
      flex-shrink: 0;
      margin-left: 16rpx;
    }
  }

  .message-wrapper {
    margin-bottom: 24rpx;
    display: flex;
    align-items: flex-start;
    gap: 16rpx;

    &.user {
      justify-content: flex-end;

      .message-bubble {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 20rpx 4rpx 20rpx 20rpx;

        .message-text {
          color: white;
        }
      }
    }

    &.assistant {
      justify-content: flex-start;

      .message-avatar {
        flex-shrink: 0;

        .avatar-circle {
          width: 56rpx;
          height: 56rpx;
          border-radius: 50%;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 4rpx 12rpx rgba(102, 126, 234, 0.3);
        }
      }

      .message-bubble {
        background: white;
        border-radius: 4rpx 20rpx 20rpx 20rpx;
        box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
      }

      &.loading {
        .message-bubble {
          background: white;
        }
      }
    }
  }

  .message-bubble {
    max-width: 75%;
    padding: 20rpx 28rpx;

    .message-text {
      font-size: 28rpx;
      line-height: 1.6;
      word-break: break-all;
      color: #333;
    }

    .loading-dots {
      display: flex;
      align-items: center;
      gap: 12rpx;
      padding: 8rpx 0;

      .dot {
        width: 12rpx;
        height: 12rpx;
        border-radius: 50%;
        background: #667eea;
        animation: dot-bounce 1.4s ease-in-out infinite;

        &:nth-child(1) {
          animation-delay: 0s;
        }

        &:nth-child(2) {
          animation-delay: 0.2s;
        }

        &:nth-child(3) {
          animation-delay: 0.4s;
        }
      }
    }
  }
}

@keyframes dot-bounce {
  0%,
  80%,
  100% {
    transform: scale(0.6);
    opacity: 0.4;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

.chat-input-area {
  padding: 20rpx 24rpx;
  background: white;
  border-top: 1rpx solid #f0f0f0;
  display: flex;
  align-items: center;
  gap: 16rpx;

  .input-wrapper {
    flex: 1;
    display: flex;
    align-items: center;
    background: #f8f9fc;
    border-radius: 36rpx;
    padding: 0 24rpx;
    gap: 12rpx;

    .input-icon {
      flex-shrink: 0;
    }
  }

  .chat-input {
    flex: 1;
    height: 72rpx;
    background: transparent;
    font-size: 28rpx;
  }

  .send-btn {
    width: 72rpx;
    height: 72rpx;
    border-radius: 50%;
    background: #e8e8e8;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.3s ease;
    flex-shrink: 0;

    &-active {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      box-shadow: 0 4rpx 16rpx rgba(102, 126, 234, 0.4);
    }
  }
}
</style>
