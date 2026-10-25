<template>
  <view class="ai-chat-panel" :class="`theme-${theme}`">
    <!-- 消息列表 -->
    <scroll-view
      class="chat-messages"
      scroll-y
      :scroll-into-view="scrollToView"
      :scroll-top="scrollTop"
    >
      <!-- 欢迎区域（快捷问题常显：有聊天记录时也保留，作为可复用的提问入口） -->
      <view
        class="welcome-section"
      >
        <view class="welcome-badge">
          <AppIcon name="lightbulb" :size="40" :color="accentColor" />
          <text class="welcome-text">您可以问我：</text>
        </view>

        <!-- 快捷问题（对齐原型 P-M10：金色描边胶囊行） -->
        <view
          v-for="(item, idx) in quickActions"
          :key="idx"
          class="quick-action-card"
          @tap="sendQuickMessage(item.text)"
        >
          <view class="card-icon-wrapper">
            <AppIcon :name="item.icon" :size="32" :color="accentColor" />
          </view>
          <text class="card-text">{{ item.text }}</text>
          <view class="card-arrow">
            <AppIcon name="arrow-right" :size="32" :color="accentColor" />
          </view>
        </view>
      </view>

      <!-- 清空会话入口（对话进行中显示在消息区顶部，避开胶囊区） -->
      <view
        v-if="showClear && messages.length > 0"
        class="clear-bar"
      >
        <view
          class="clear-pill"
          :class="{ 'clear-disabled': isLoading }"
          @tap="clearHistory"
        >
          <AppIcon name="trash" :size="24" :color="clearColor" />
          <text class="clear-pill-text">清空会话</text>
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
        <view class="message-bubble" :class="{ error: msg.isError }">
          <view class="message-text">
            <view
              v-for="(line, li) in messageLines(msg.content)"
              :key="li"
              class="message-line"
              :class="{ hang: line.startsWith('- ') || line.startsWith('• ') }"
            >{{ line || " " }}</view>
          </view>
          <view
            v-if="msg.isError"
            class="retry-btn"
            :class="{ 'retry-disabled': isLoading }"
            @tap="retryLastMessage"
          >
            <text class="retry-text">重试</text>
          </view>
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
          :maxlength="500"
          :adjust-position="true"
          :cursor-spacing="20"
          confirm-type="send"
          @confirm="sendMessage"
        />
      </view>
      <view
        class="send-btn"
        :class="{ 'send-btn-active': !!inputText.trim() }"
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
</template>

<script setup lang="ts">
import { aiChatApi } from "@/api";
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import AppIcon from "./AppIcon.vue";

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  isError?: boolean;
}

const props = withDefaults(
  defineProps<{
    sessionId?: string;
    /** violet: 教师端弹窗原配色；champagne: 学员端香槟金主题 */
    theme?: "violet" | "champagne";
    /** 是否显示"清空会话"入口（显示在消息区顶部，学员端整页使用；教师端弹窗默认关闭） */
    showClear?: boolean;
    /** 是否在挂载时恢复历史会话（教师端弹窗默认开启；学员端整页传 false，每次进入为空白新会话） */
    autoRestoreHistory?: boolean;
  }>(),
  {
    sessionId: "",
    theme: "violet",
    showClear: false,
    autoRestoreHistory: true,
  },
);

const emit = defineEmits<{
  (e: "message-sent", payload: {
    userMessage: string;
    aiResponse: string;
  }): void;
}>();

const accentColor = computed(() =>
  props.theme === "champagne" ? "#c9a66b" : "#667eea",
);

const clearColor = computed(() =>
  props.theme === "champagne" ? "#8b7355" : "#667eea",
);

const messages = ref<Message[]>([]);
const inputText = ref("");
const isLoading = ref(false);
const scrollToView = ref("");
const scrollTop = ref(0);

// 快捷问题（对齐原型 P-M10：单行问题文本 + 金色描边胶囊）
const quickActions = [
  { text: "帮我查一下有哪些课程", icon: "book" as const },
  { text: "帮我约一节瑜伽课", icon: "calendar" as const },
  { text: "我的课时余额还剩多少", icon: "wallet" as const },
  { text: "查看我的预约记录", icon: "clipboard" as const },
];

const buildSessionId = (): string => {
  if (props.sessionId) return props.sessionId;

  const userInfo = uni.getStorageSync("userInfo");
  const userId = userInfo?.id || userInfo?.user_id || "anon";
  return `session_${userId}`;
};

let currentSessionId = buildSessionId();

/** AI 返回的多行文本按行渲染：折行内容通过悬挂缩进与列表项文字起点对齐 */
const messageLines = (content: string): string[] => (content || "").split("\n");

onMounted(() => {
  if (props.autoRestoreHistory) loadHistory();
  uni.$on("login-success", handleLoginSuccess);
});

onBeforeUnmount(() => {
  uni.$off("login-success", handleLoginSuccess);
});

const handleLoginSuccess = () => {
  currentSessionId = buildSessionId();
  messages.value = [];
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

const doSend = async (text: string) => {
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
        isError: true,
      });
    }
  } catch (error: any) {
    console.error("AI 对话失败:", error);
    messages.value.push({
      role: "assistant",
      content: "网络错误，请检查连接后重试",
      timestamp: Date.now(),
      isError: true,
    });
  } finally {
    isLoading.value = false;
    scrollToBottom();
  }
};

const sendMessage = (evt?: unknown) => {
  // 支持 confirm 事件对象与直接字符串调用
  const raw = typeof evt === "string" ? evt : inputText.value;
  const text = raw.trim();
  if (!text || isLoading.value) return;

  inputText.value = "";
  void doSend(text);
};

const retryLastMessage = () => {
  if (isLoading.value) return;

  // 移除末尾的错误消息，重发最后一条用户消息
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const msg = messages.value[i];
    if (msg.role === "assistant" && !msg.isError) return;
    if (msg.role === "user") {
      const text = msg.content;
      messages.value = messages.value.slice(0, i);
      void doSend(text);
      return;
    }
  }
};

const sendQuickMessage = (text: string) => {
  if (isLoading.value) return;
  sendMessage(text);
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
  clearHistory,
  sendMessage,
  loadHistory,
});
</script>

<style lang="scss" scoped>
.ai-chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;

  // 主题变量：violet（教师端弹窗原配色，默认）
  --ai-grad: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  --ai-accent: #667eea;
  --ai-accent-soft: rgba(102, 126, 234, 0.08);
  --ai-accent-bg: #f0f0ff;
  --ai-shadow-color: rgba(102, 126, 234, 0.4);
  --ai-msgs-bg: #f8f9fc;
  --ai-text: #333333;
  --ai-badge-text: #333333;
  --ai-q-border: #e8e8f5;
  --ai-q-text: #555555;
  --ai-clear-border: #d8dcf5;
  --ai-input-bg: #f8f9fc;
  --ai-input-border: transparent;

  // 主题变量：champagne（学员端香槟金，对齐原型 P-M10 取值）
  &.theme-champagne {
    --ai-grad: linear-gradient(135deg, #c9a66b 0%, #d4b896 100%);
    --ai-accent: #c9a66b;
    --ai-accent-soft: rgba(201, 166, 107, 0.14);
    --ai-accent-bg: rgba(201, 166, 107, 0.16);
    --ai-shadow-color: rgba(201, 166, 107, 0.4);
    // 原型 .ai-page 背景：浅米金渐变
    --ai-msgs-bg: linear-gradient(180deg, #faf6f0 0%, #f5ede3 100%);
    --ai-text: #3a2c1e;
    --ai-badge-text: #8b7355;
    --ai-q-border: #efe6d8;
    --ai-q-text: #5a4a38;
    --ai-clear-border: #e6dccd;
    --ai-input-bg: #faf7f2;
    --ai-input-border: #eee3d5;
  }
}

.chat-messages {
  flex: 1;
  min-height: 0;
  padding: 24rpx 24rpx 12rpx;
  background: var(--ai-msgs-bg);
  box-sizing: border-box;

  .welcome-section {
    padding: 20rpx 0;

    .welcome-badge {
      display: inline-flex;
      align-items: center;
      gap: 12rpx;
      background: var(--ai-accent-soft);
      padding: 16rpx 28rpx;
      border-radius: 40rpx;
      margin: 0 auto 32rpx;
      width: fit-content;

      .welcome-text {
        font-size: 28rpx;
        font-weight: 600;
        color: var(--ai-badge-text);
      }
    }
  }

  // 清空会话入口（消息区顶部，小字描边胶囊，避开右上角胶囊区）
  .clear-bar {
    display: flex;
    justify-content: center;
    margin-bottom: 20rpx;

    .clear-pill {
      display: inline-flex;
      align-items: center;
      gap: 8rpx;
      padding: 8rpx 24rpx;
      border-radius: 999rpx;
      border: 1rpx solid var(--ai-clear-border);
      background: transparent;

      &:active {
        opacity: 0.7;
      }

      &.clear-disabled {
        opacity: 0.5;
      }

      .clear-pill-text {
        font-size: 22rpx;
        color: var(--ai-badge-text);
      }
    }
  }

  // 快捷问题：金色描边胶囊行（对齐原型 .ai-qcard）
  .quick-action-card {
    display: flex;
    align-items: center;
    gap: 16rpx;
    background: white;
    border: 1rpx solid var(--ai-q-border);
    padding: 20rpx 24rpx;
    margin-bottom: 16rpx;
    border-radius: 20rpx;
    box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.04);

    &:active {
      transform: scale(0.98);
      opacity: 0.85;
    }

    .card-icon-wrapper {
      width: 52rpx;
      height: 52rpx;
      border-radius: 16rpx;
      background: var(--ai-accent-bg);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }

    .card-text {
      flex: 1;
      min-width: 0;
      font-size: 26rpx;
      color: var(--ai-q-text);
    }

    .card-arrow {
      flex-shrink: 0;
      display: flex;
      align-items: center;
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
        background: var(--ai-grad);
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
          background: var(--ai-grad);
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 4rpx 12rpx var(--ai-shadow-color);
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
      color: var(--ai-text);

      .message-line {
        white-space: pre-wrap;

        // "- "/"• " 开头的列表行：折行内容对齐到文字起点（悬挂缩进），而非顶格
        &.hang {
          padding-left: 1em;
          text-indent: -1em;
        }
      }
    }

    &.error {
      background: rgba(255, 71, 87, 0.08);
      border: 1rpx solid rgba(255, 71, 87, 0.25);

      .message-text {
        color: #d63031;
      }

      .retry-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin-top: 14rpx;
        padding: 8rpx 28rpx;
        background: #ff4757;
        border-radius: 24rpx;

        &:active {
          opacity: 0.8;
        }

        &.retry-disabled {
          opacity: 0.5;
        }

        .retry-text {
          font-size: 24rpx;
          color: #fff;
          font-weight: 500;
        }
      }
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
        background: var(--ai-accent);
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
  flex-shrink: 0;
  padding: 20rpx 24rpx;
  background: white;
  border-top: 1rpx solid #f0f0f0;
  display: flex;
  align-items: center;
  gap: 16rpx;
  box-sizing: border-box;

  .input-wrapper {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    background: var(--ai-input-bg);
    border: 1rpx solid var(--ai-input-border);
    border-radius: 36rpx;
    padding: 0 24rpx;
    gap: 12rpx;
    box-sizing: border-box;

    .input-icon {
      flex-shrink: 0;
      display: flex;
      align-items: center;
    }
  }

  // 关键修复：小程序原生 textarea 有固有宽度（约 300px），不受 flex 收缩约束，
  // 必须显式限制 width:100% + box-sizing，否则会把 input-wrapper 撑破，
  // 导致右侧发送按钮被推出屏幕边缘裁切一半。
  .chat-input {
    flex: 1;
    width: 100%;
    min-width: 0;
    height: 72rpx;
    min-height: 72rpx;
    max-height: 72rpx;
    background: transparent;
    font-size: 28rpx;
    line-height: 72rpx;
    padding: 0;
    box-sizing: border-box;
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
      background: var(--ai-grad);
      box-shadow: 0 4rpx 16rpx var(--ai-shadow-color);
    }
  }
}
</style>
