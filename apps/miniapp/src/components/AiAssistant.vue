<template>
  <view class="ai-assistant">
    <!-- 悬浮按钮 -->
    <view 
      v-if="isLoggedIn"
      class="ai-fab" 
      :class="{ 'ai-fab-active': isVisible }"
      @tap="toggleChat"
    >
      <text class="ai-fab-icon">{{ isVisible ? '✕' : '🤖' }}</text>
      <view v-if="unreadCount > 0" class="ai-badge">
        {{ unreadCount > 99 ? '99+' : unreadCount }}
      </view>
    </view>

    <!-- 聊天窗口 -->
    <view v-if="isVisible" class="ai-chat-window">
      <!-- 头部 -->
      <view class="chat-header">
        <text class="chat-title">🤖 AI 助手</text>
        <view class="chat-actions">
          <text class="action-btn" @tap.stop="clearHistory">清空</text>
        </view>
      </view>

      <!-- 消息列表 -->
      <scroll-view 
        class="chat-messages" 
        scroll-y 
        :scroll-into-view="scrollToView"
        :scroll-top="scrollTop"
      >
        <view 
          v-for="(msg, index) in messages" 
          :id="'msg-' + index"
          :key="index"
          class="message-wrapper"
          :class="msg.role"
        >
          <view class="message-bubble">
            <text class="message-text">{{ msg.content }}</text>
          </view>
        </view>

        <!-- 加载中 -->
        <view v-if="isLoading" class="message-wrapper assistant">
          <view class="message-bubble loading">
            <text class="typing-dots">思考中...</text>
          </view>
        </view>

        <!-- 快捷入口（首次打开时显示） -->
        <view v-if="messages.length === 0 && !isLoading" class="quick-actions">
          <text class="quick-title">💡 您可以问我：</text>
          <view 
            v-for="(item, idx) in quickActions" 
            :key="idx"
            class="quick-item"
            @tap="sendQuickMessage(item.text)"
          >
            <text>{{ item.label }}</text>
          </view>
        </view>
      </scroll-view>

      <!-- 输入框 -->
      <view class="chat-input-area">
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
        <view 
          class="send-btn"
          :class="{ 'send-btn-active': inputText.trim() }"
          @tap="sendMessage"
        >
          <text>发送</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { aiChatApi } from '@/api'

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

const props = withDefaults(defineProps<{
  sessionId?: string
}>(), {
  sessionId: () => `student_${Date.now()}`
})

const emit = defineEmits<{
  (e: 'booking-created', data: any): void
  (e: 'booking-cancelled', bookingId: number): void
}>()

const isLoggedIn = ref(false)
const isVisible = ref(false)
const messages = ref<Message[]>([])
const inputText = ref('')
const isLoading = ref(false)
const isInputFocused = ref(false)
const unreadCount = ref(0)
const scrollToView = ref('')
const scrollTop = ref(0)

const quickActions = [
  { label: '📚 查询课程', text: '帮我查一下有哪些课程' },
  { label: '📅 预约课程', text: '帮我约一节瑜伽课' },
  { label: '💰 查询余额', text: '我的课时余额还剩多少' },
  { label: '📋 我的预约', text: '查看我的预约记录' }
]

let currentSessionId = props.sessionId

const checkLogin = () => {
  const token = uni.getStorageSync('token')
  isLoggedIn.value = !!token
}

onMounted(() => {
  checkLogin()
  uni.$on('login-success', checkLogin)
})

onBeforeUnmount(() => {
  uni.$off('login-success', checkLogin)
})

const toggleChat = () => {
  isVisible.value = !isVisible.value
  if (isVisible.value) {
    unreadCount.value = 0
    loadHistory()
  }
}

const loadHistory = async () => {
  try {
    const res = await aiChatApi.getHistory(currentSessionId)
    if (res.code === 0 || res.code === 200) {
      messages.value = (res.data || []).map((msg: any) => ({
        role: msg.role,
        content: msg.content,
        timestamp: Date.now()
      }))
      scrollToBottom()
    }
  } catch (error) {
    console.error('加载历史记录失败:', error)
  }
}

const sendMessage = async () => {
  const text = inputText.value.trim()
  if (!text || isLoading.value) return

  inputText.value = ''
  
  messages.value.push({
    role: 'user',
    content: text,
    timestamp: Date.now()
  })

  isLoading.value = true
  scrollToBottom()

  try {
    const res = await aiChatApi.chat(text, currentSessionId)
    
    if (res.code === 0 || res.code === 200) {
      const aiResponse = res.data?.response || res.msg || '抱歉，我暂时无法回答'
      
      messages.value.push({
        role: 'assistant',
        content: aiResponse,
        timestamp: Date.now()
      })

      emit('message-sent', { userMessage: text, aiResponse })
    } else {
      messages.value.push({
        role: 'assistant',
        content: res.msg || '请求失败，请稍后重试',
        timestamp: Date.now()
      })
    }
  } catch (error: any) {
    console.error('AI 对话失败:', error)
    messages.value.push({
      role: 'assistant',
      content: '网络错误，请检查连接后重试',
      timestamp: Date.now()
    })
  } finally {
    isLoading.value = false
    scrollToBottom()
  }
}

const sendQuickMessage = (text: string) => {
  inputText.value = text
  sendMessage()
}

const clearHistory = async () => {
  uni.showModal({
    title: '提示',
    content: '确定要清空聊天记录吗？',
    success: async (res) => {
      if (res.confirm) {
        try {
          await aiChatApi.clearHistory(currentSessionId)
          messages.value = []
          uni.showToast({ title: '已清空', icon: 'success' })
        } catch (error) {
          uni.showToast({ title: '清空失败', icon: 'none' })
        }
      }
    }
  })
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messages.value.length > 0) {
      scrollToView.value = `msg-${messages.value.length - 1}`
      scrollTop.value = Math.random() * 100
    }
  })
}

defineExpose({
  toggleChat,
  sendMessage
})
</script>

<style lang="scss" scoped>
.ai-assistant {
  position: fixed;
  z-index: 9999;
  right: 30rpx;
  bottom: 200rpx;
}

.ai-fab {
  width: 100rpx;
  height: 100rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  box-shadow: 0 8rpx 24rpx rgba(102, 126, 234, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.3s ease,
              box-shadow 0.3s ease;
  
  &-active {
    transform: rotate(90deg);
  }

  &-icon {
    font-size: 48rpx;
    color: white;
  }
}

.ai-badge {
  position: absolute;
  top: -10rpx;
  right: -10rpx;
  background: #ff4757;
  color: white;
  font-size: 20rpx;
  padding: 4rpx 12rpx;
  border-radius: 20rpx;
  min-width: 32rpx;
  text-align: center;
}

.ai-chat-window {
  position: fixed;
  right: 20rpx;
  bottom: 340rpx;
  width: 650rpx;
  height: 800rpx;
  background: white;
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

  .chat-title {
    font-size: 34rpx;
    font-weight: 600;
    color: white;
  }

  .action-btn {
    font-size: 26rpx;
    color: rgba(255, 255, 255, 0.9);
    padding: 8rpx 16rpx;
  }
}

.chat-messages {
  flex: 1;
  padding: 24rpx;
  background: #f5f6fa;
  overflow-y: auto;

  .message-wrapper {
    margin-bottom: 24rpx;
    display: flex;

    &.user {
      justify-content: flex-end;

      .message-bubble {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 20rpx 20rpx 4rpx 20rpx;
        
        .message-text {
          color: white;
        }
      }
    }

    &.assistant {
      justify-content: flex-start;

      .message-bubble {
        background: white;
        border-radius: 20rpx 20rpx 20rpx 4rpx;
        box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
      }

      &.loading {
        background: #f0f0f0;
      }
    }
  }

  .message-bubble {
    max-width: 80%;
    padding: 20rpx 28rpx;

    .message-text {
      font-size: 28rpx;
      line-height: 1.5;
      word-break: break-all;
    }

    .typing-dots {
      color: #999;
      font-size: 26rpx;
    }
  }
}

.quick-actions {
  margin-top: 40rpx;

  .quick-title {
    font-size: 26rpx;
    color: #666;
    display: block;
    margin-bottom: 20rpx;
  }

  .quick-item {
    background: white;
    padding: 20rpx 28rpx;
    margin-bottom: 16rpx;
    border-radius: 12rpx;
    font-size: 28rpx;
    color: #333;
    box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);

    &:active {
      background: #f5f5f5;
    }
  }
}

.chat-input-area {
  padding: 20rpx 24rpx;
  background: white;
  border-top: 1rpx solid #eee;
  display: flex;
  align-items: center;
  gap: 16rpx;

  .chat-input {
    flex: 1;
    height: 72rpx;
    background: #f5f6fa;
    border-radius: 36rpx;
    padding: 0 28rpx;
    font-size: 28rpx;
  }

  .send-btn {
    width: 120rpx;
    height: 72rpx;
    background: #ccc;
    border-radius: 36rpx;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.3s,
              transform 0.3s;

    &-active {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);

      text {
        color: white;
      }
    }

    text {
      font-size: 28rpx;
      color: white;
    }
  }
}
</style>