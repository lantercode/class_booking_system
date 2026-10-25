<template>
  <view class="ai-page">
    <!-- 顶部标题区（香槟金渐变，对齐原型 P-M10：图标 + 标题 + 副标题，无清空按钮） -->
    <view class="ai-page-header" :style="{ paddingTop: statusBarHeight + 'px' }">
      <view class="header-row" :style="{ minHeight: navContentHeight + 'px' }">
        <view class="header-icon-wrapper">
          <AppIcon name="ai-robot" :size="44" color="#fff" />
        </view>
        <view class="header-text">
          <text class="chat-title">AI 助手</text>
          <text class="chat-subtitle">智能课程助手</text>
        </view>
      </view>
    </view>

    <!-- 共享聊天面板（消息流 + 快捷问题 + 输入区，走真实 aiChatApi） -->
    <AiChatPanel
      :session-id="sessionId"
      theme="champagne"
      :show-clear="true"
      :auto-restore-history="false"
      class="ai-page-panel"
    />

    <HomeTabBar currentRoute="/pages/student/ai-assistant/index" />
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import AiChatPanel from "@/components/AiChatPanel.vue";
import AppIcon from "@/components/AppIcon.vue";
import HomeTabBar from "@/components/HomeTabBar.vue";
import { checkLogin, getUserId } from "@/utils/auth";

// 与 AppNavbar / schedule 等自定义导航页一致的安全区适配：
// paddingTop = 状态栏高度；内容行高度 = max(胶囊高度 + 10, 44)，右侧预留胶囊区宽度
const systemInfo = uni.getSystemInfoSync();
const menuButton = uni.getMenuButtonBoundingClientRect();
const statusBarHeight = systemInfo.statusBarHeight ?? 0;
const navContentHeight = Math.max((menuButton.height || 32) + 10, 44);

const userId = ref<string>("");

// 每次进入页面使用全新会话 ID：不恢复历史消息，服务端对话上下文也从空白开始
const entryTs = Date.now();
const sessionId = computed(() => `student_${userId.value || "default"}_${entryTs}`);

onMounted(() => {
  if (!checkLogin("student")) return;

  const uid = getUserId();
  userId.value = uid != null ? String(uid) : "";
});
</script>

<style lang="scss" scoped>
.ai-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f8f9fc;
  // 底部为 HomeTabBar 预留空间：TabBar 实际高约 132rpx（12+28 padding+内容），另留约 28rpx 呼吸间隙
  padding-bottom: 160rpx;
  box-sizing: border-box;
  overflow: hidden;
}

.ai-page-header {
  background: linear-gradient(135deg, #8b7355 0%, #c9a66b 100%);
  padding-bottom: 24rpx;
  flex-shrink: 0;

  .header-row {
    display: flex;
    align-items: center;
    gap: 16rpx;
    box-sizing: border-box;
    // 右侧预留微信胶囊按钮区（"... ⊙" 约占 174rpx），标题不进入胶囊区
    padding: 8rpx 190rpx 0 32rpx;
  }

  .header-icon-wrapper {
    width: 72rpx;
    height: 72rpx;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.2);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .header-text {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4rpx;

    .chat-title {
      font-size: 34rpx;
      font-weight: 600;
      color: #fff;
    }

    .chat-subtitle {
      font-size: 22rpx;
      color: rgba(255, 255, 255, 0.8);
    }
  }
}

.ai-page-panel {
  flex: 1;
  min-height: 0;
}
</style>
