# 🤖 AI 智能助手 - 小程序端集成指南

## ✨ 功能特性

- 💬 **多轮对话**：支持自然语言交互（"帮我约瑜伽课" → "选第 1 个"）
- 🎯 **意图识别**：自动理解用户需求（查课程/预约/取消/余额）
- 🔒 **状态管理**：Redis 持久化，支持跨页面对话
- ⚡ **实时响应**：流式输出，用户体验流畅
- 🛡️ **企业级**：分布式锁、错误码、结构化日志

---

## 🚀 快速开始

### 1. 前置条件

```bash
# 确保后端服务已启动
cd apps/api
PYTHONPATH=src .venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 配置 API 地址

编辑 `apps/miniapp/.env`：

```env
VITE_API_BASE_URL=http://你的IP:8000/api/v1
```

**注意**：
- 开发环境使用局域网 IP（如 `192.168.0.100`）
- 生产环境使用域名（如 `https://api.yourdomain.com`）

### 3. 编译小程序

```bash
cd apps/miniapp
npm run dev:mp-weixin
```

然后在微信开发者工具中导入 `dist/dev/mp-weixin` 目录。

---

## 📱 使用方式

### 方式 1：悬浮按钮（已集成到"我的"页面）

1. 进入 **「我的」** 页面
2. 点击右下角 **🤖 按钮**
3. 在弹出的聊天窗口中输入问题

**示例对话**：

```
用户：帮我约一节瑜伽课
AI：📅 找到以下排期，请回复数字选择：

    [1] 2026-08-16 14:00-15:00 王老师（剩余5个）
    [2] 2026-08-16 16:00-17:00 李老师（剩余3个）

用户：1
AI：✅ 预约成功！

    📚 课程：瑜伽课
    📅 时间：2026-08-16 14:00-15:00
    👨‍🏫 老师：王老师
```

### 支持的快捷指令

| 指令 | 示例 | 说明 |
|------|------|------|
| 查课程 | "有哪些课程"、"瑜伽课信息" | 返回课程列表 |
| 查排期 | "明天有什么课"、"下午的排期" | 返回可用时段 |
| 预约课程 | "帮我约瑜伽课"、"预约 ID:5 的课" | 多轮选择或直接预约 |
| 取消预约 | "取消预约 1001" | 二次确认后执行 |
| 查余额 | "我的余额"、"还剩多少课时" | 返回课时统计 |
| 查预约记录 | "我的预约"、"最近预约了什么" | 返回历史记录 |

---

## 🎨 自定义配置

### 修改主题色

编辑 `AiAssistant.vue` 的 `<style>` 部分：

```scss
// 当前配色（紫蓝渐变）
.ai-fab {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

// 改为品牌色（示例：橙色）
.ai-fab {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}
```

### 调整位置和大小

```vue
<AiAssistant 
  :session-id="'student_' + userInfo.id"
  :position="'bottom-right'"  // 可选: 'bottom-left'
  :size="'large'"             // 可选: 'small', 'medium', 'large'
/>
```

### 隐藏/显示按钮

```vue
<script setup>
import { ref } from 'vue'
import AiAssistant from '@/components/AiAssistant.vue'

const showAi = ref(true)

// 根据条件控制显示
const toggleAi = () => {
  showAi.value = !showAi.value
}
</script>

<template>
  <AiAssistant v-if="showAi" />
</template>
```

---

## 🔧 高级用法

### 1. 全局引入（所有页面都显示）

在 `App.vue` 中添加：

```vue
<template>
  <!-- 其他内容 -->
  <AiAssistant />
</template>

<script setup>
import AiAssistant from '@/components/AiAssistant.vue'
</script>
```

### 2. 在特定页面嵌入

#### 课程详情页 - 智能推荐

```vue
<!-- pages/student/courses/detail.vue -->
<template>
  <view>
    <!-- 课程信息 -->
    
    <!-- AI 快捷操作 -->
    <view class="ai-quick-actions">
      <button @tap="askAi('帮我约这门课')">🤖 AI 帮我约</button>
      <button @tap="askAi('这门课的老师怎么样')">❓ 问 AI</button>
    </view>
    
    <AiAssistant ref="aiAssistant" />
  </view>
</template>

<script setup>
const aiAssistant = ref()

const askAi = (question) => {
  aiAssistant.value?.toggleChat()
  aiAssistant.value?.sendMessage(question)
}
</script>
```

#### 预约列表页 - 一键取消

```vue
<!-- pages/student/bookings/index.vue -->
<template>
  <view>
    <view 
      v-for="booking in bookings" 
      class="booking-item"
    >
      {{ booking.course_name }}
      
      <button @tap="cancelWithAi(booking.id)">
        🤖 AI 取消
      </button>
    </view>
    
    <AiAssistant ref="aiAssistant" />
  </view>
</template>

<script setup>
const aiAssistant = ref()

const cancelWithAi = (bookingId) => {
  aiAssistant.value?.toggleChat()
  aiAssistant.value?.sendMessage(`取消预约 ${bookingId}`)
}
</script>
```

### 3. 与业务逻辑联动

```vue
<script setup>
const handleAiMessage = (data) => {
  const { userMessage, aiResponse } = data
  
  // 预约成功 → 刷新列表、发送通知
  if (aiResponse.includes('预约成功')) {
    refreshBookingList()
    sendPushNotification('预约成功提醒')
  }
  
  // 余额不足 → 跳转充值页
  if (aiResponse.includes('课时不足')) {
    uni.navigateTo({ url: '/pages/recharge/index' })
  }
  
  // 错误处理 → 上报监控
  if (aiResponse.includes('错误')) {
    reportErrorToMonitor({
      source: 'ai-assistant',
      message: aiResponse,
      userInput: userMessage
    })
  }
}
</script>
```

---

## 🐛 常见问题

### Q1：点击按钮没反应？

**检查项**：
1. 后端服务是否启动（`http://localhost:8000/docs` 能否打开）
2. API 地址是否正确（`.env` 中的 `VITE_API_BASE_URL`）
3. 手机/模拟器能否访问后端（同一局域网）

**调试方法**：
```javascript
// 在微信开发者工具 Console 中查看
console.log('API Base URL:', import.meta.env.VITE_API_BASE_URL)
```

### Q2：AI 回复很慢？

**可能原因**：
1. LLM 推理延迟（首次调用较慢，后续会快）
2. 网络延迟（检查手机 WiFi）
3. 后端负载高（查看服务器 CPU/内存）

**优化建议**：
- 添加加载动画（已内置 `思考中...`）
- 设置超时时间（当前 30 秒）
- 考虑使用流式响应（SSE/WebSocket）

### Q3：多轮对话状态丢失？

**排查步骤**：
1. 检查 Redis 是否运行：`redis-cli ping`
2. 查看 Redis 中的状态：`redis-cli GET "ai:state:session_xxx"`
3. 检查 TTL 是否过期（默认 10 分钟）

**临时方案**：
如果 Redis 不可用，系统会降级为单轮模式（每次都需要完整描述需求）。

### Q4：如何限制使用频率？

在后端添加限流中间件：

```python
# apps/api/src/app/main.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/v1/ai/chat")
@limiter.limit("10/minute")  # 每分钟最多 10 次
async def chat(request: Request, body: ChatRequest):
    ...
```

---

## 📊 监控与日志

### 关键指标

| 指标 | 说明 | 告警阈值 |
|------|------|---------|
| `ai_chat_total` | 总请求数 | - |
| `ai_chat_success_rate` | 成功率 | < 95% |
| `ai_chat_latency_p99` | P99 延迟 | > 5s |
| `ai_intent_recognition_rate` | 意图识别准确率 | < 80% |

### 日志示例

```
2026-08-15 18:21:19 INFO 意图识别: session=student_123, intent=create_booking, params={'keyword': '瑜伽课'}
2026-08-15 18:21:20 INFO 存入取消确认状态: session=student_123, booking_id=1001
2026-08-15 18:21:25 INFO 用户选择排期: session=student_123, selection=1, schedule_id=5
2026-08-15 18:21:26 INFO 预约成功: session=student_123, schedule_id=5, user_id=1
```

---

## 🚀 下一步优化方向

### 短期（1-2 周）
- [ ] 添加语音输入支持（微信同声传译插件）
- [ ] 实现流式响应（SSE）提升体验
- [ ] 添加常用问题 FAQ 知识库

### 中期（1 个月）
- [ ] 接入真实 LLM（如 GPT-4、文心一言）
- [ ] 添加用户反馈机制（点赞/点踩）
- [ ] 实现对话上下文记忆（跨会话）

### 长期（3 个月+）
- [ ] 多模态支持（图片识别课程表）
- [ ] 个性化推荐（基于历史预约）
- [ ] 主动推送（上课提醒、优惠活动）

---

## 📞 技术支持

如有问题，请联系：
- **后端 API**：查看 `/apps/api` 目录
- **小程序代码**：查看 `/apps/miniapp/src/components/AiAssistant.vue`
- **API 接口文档**：`http://localhost:8000/docs`（Swagger UI）

---

**最后更新**：2026-08-15  
**版本**：v1.0.0（Day 5 企业级版本）