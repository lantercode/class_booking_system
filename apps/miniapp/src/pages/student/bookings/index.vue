<template>
  <view class="book-container">
    <!-- 自定义导航栏 - 统一使用AppNavbar -->
    <AppNavbar
      title=""
      :show-back="false"
      variant="default"
    >
      <template #left>
        <view>预约</view>
      </template>
    </AppNavbar>

    <!-- 主内容区域 - 参照课程页面结构 -->
    <view class="main-content">
      <!-- 筛选标签 - 使用统一组件 -->
      <AppFilterTabs
        v-model="activeFilter"
        :tabs="filterTabs"
        @change="loadBookings"
      />

      <!-- 可滚动内容区域 - 动态控制滚动行为 -->
      <scroll-view
        :scroll-y="bookings.length > 0"
        class="booking-list"
        :style="{ height: scrollViewHeight + 'px' }"
        :class="{ 'no-scroll': bookings.length === 0 }"
        :show-scrollbar="false"
        @scrolltolower="onScrollToLower"
      >
      <!-- 空状态 -->
      <view v-if="bookings.length === 0" class="empty-state">
        <text class="empty-icon">📝</text>
        <text class="empty-text">暂无预约</text>
        <button class="empty-btn" @tap="goToCourses">去预约课程</button>
      </view>

      <!-- 预约列表 - 使用 view 包裹确保渲染 -->
      <view class="booking-list-inner">
        <view
          v-for="(booking, index) in bookings"
          :key="booking.id || index"
          class="booking-card"
          :style="{ animationDelay: `${index * 0.04}s` }"
        >
          <view class="booking-status-bar" :class="getStatusClass(booking.status)"></view>
          <view class="booking-content">
            <view class="booking-header">
              <text class="course-name">{{ booking.course_name || '未知课程' }}</text>
              <text class="booking-status" :class="getStatusClass(booking.status)">
                {{ getStatusText(booking.status) }}
              </text>
            </view>
            <view class="booking-info">
              <text class="booking-date">{{ formatDateTime(booking.start_at) }}</text>
              <text class="classroom">📍 {{ booking.classroom_name || '未安排' }}</text>
              <text class="teacher">👨‍🏫 {{ booking.teacher_name || '未知' }}</text>
            </view>
            <view class="booking-footer">
              <text class="booking-time">预约时间: {{ formatTime(booking.created_at) }}</text>
              <view v-if="Number(booking.status) === BOOKING_STATUS.BOOKED" class="booking-actions">
                <button class="action-btn cancel" @tap="handleCancel(booking.id)">取消预约</button>
              </view>
            </view>
          </view>
        </view>
      </view>
    </scroll-view>

    </view><!-- /main-content -->

    <StudentTabBar currentRoute="/pages/student/bookings/index" />

    <!-- AI 智能助手 -->
    <AiAssistant
      :session-id="'student_' + (userId || 'default')"
    />
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { bookingApi } from '@/api'
import { checkLogin, getUserId } from '@/utils/auth'
import { formatDateTime, formatTime } from '@/utils/date'
import StudentTabBar from '@/components/StudentTabBar.vue'
import AppNavbar from '@/components/AppNavbar.vue'
import AppFilterTabs from '@/components/AppFilterTabs.vue'
import AiAssistant from '@/components/AiAssistant.vue'
import { navigateTo } from '@/utils/navigation'
import { extractList } from '@/utils/helpers'

const BOOKING_STATUS = {
  ALL: 'all',
  BOOKED: 1,        // 已预约（待上课）
  CHECKED_IN: 3,    // 已签到
  COMPLETED: 4,     // 已完成
  CANCELLED: 2      // 已取消
} as const

const activeFilter = ref<string | number>('all')
const bookings = ref<any[]>([])
const userId = ref('')

const systemInfo = uni.getSystemInfoSync()
const navbarHeight = systemInfo.statusBarHeight + 44
const tabbarHeight = (100 / 750) * systemInfo.windowWidth
const scrollViewHeight = ref(Math.max(
  systemInfo.windowHeight - navbarHeight - tabbarHeight - 110,
  400
))

// ✅ 页面卸载标记
let isUnmounted = false

// ✅ 不再需要手动计算 scrollHeight，使用 CSS Flex 布局自动填充

const filterTabs = [
  { label: '全部', value: BOOKING_STATUS.ALL },
  { label: '待上课', value: BOOKING_STATUS.BOOKED },
  { label: '已签到', value: BOOKING_STATUS.CHECKED_IN },
  { label: '已完成', value: BOOKING_STATUS.COMPLETED },
  { label: '已取消', value: BOOKING_STATUS.CANCELLED }
]

onMounted(() => {
  console.log('\n📱 ===== 我的预约页面 - onMounted 触发 =====\n')

  const isLoggedIn = checkLogin('student')
  console.log('✓ checkLogin 结果:', isLoggedIn)

  if (!isLoggedIn) {
    console.warn('⚠️ 用户未登录或角色不匹配，停止加载')
    return
  }

  console.log('✓ 用户已登录，开始初始化页面')

  userId.value = String(getUserId() || '')

  console.log('🚀 准备调用 loadBookings()...')
  loadBookings()
})

onUnmounted(() => {
  isUnmounted = true
})

// ✅ 滚动到底部事件（可选，用于加载更多）
const onScrollToLower = () => {
  console.log('📜 滚动到底部')
  // 可以在这里实现分页加载
}

const loadBookings = async () => {
  try {
    console.log('\n🚀 ===== 开始加载我的预约列表 =====\n')

    // Step 1: 准备参数
    const params: any = {}
    
    if (activeFilter.value !== 'all') {
      params.status = activeFilter.value
    }

    console.log('📋 Step 1 - 请求参数:', JSON.stringify(params))

    // Step 2: 发起 API 请求（添加超时控制）
    console.log('📡 Step 2 - 正在调用 bookingApi.list()...')
    
    let result: any
    try {
      // 设置 10 秒超时
      const timeoutPromise = new Promise((_, reject) => 
        setTimeout(() => reject(new Error('API 请求超时 (>10s)')), 10000)
      )
      
      result = await Promise.race([
        bookingApi.list(params),
        timeoutPromise
      ])
      
      // ✅ 页面已卸载，不再更新数据
      if (isUnmounted) return
      
      console.log('✅ Step 2 - API 请求成功！')
      
    } catch (apiError: any) {
      console.error('❌ Step 2 - API 请求失败:', apiError.message || apiError)
      throw new Error(`API 请求失败: ${apiError.message || apiError}`)
    }

    // Step 3: 分析返回结果
    console.log('\n🔍 Step 3 - 分析 API 返回数据:')
    console.log('-'.repeat(50))
    console.log('result 完整内容:')
    console.log(JSON.stringify(result, null, 2))
    console.log('-'.repeat(50))
    
    // 检查 result 本身
    if (!result) {
      throw new Error('API 返回为空 (null/undefined)')
    }
    
    console.log('✓ result 存在')
    console.log('  - 类型:', typeof result)
    console.log('  - code:', result.code)
    console.log('  - msg:', result.msg)

    // Step 4: 提取 data
    console.log('\n📦 Step 4 - 提取 result.data:')
    
    const rawData = result.data
    console.log('rawData:', rawData)
    console.log('rawData 类型:', typeof rawData)
    console.log('rawData 是否为 null/undefined:', rawData == null)

    if (rawData == null) {
      console.warn('⚠️ rawData 为 null 或 undefined，尝试使用整个 result')
      // 有些 API 直接返回数组，不在 data 字段中
      if (Array.isArray(result)) {
        console.log('✓ result 本身是数组，直接使用')
        bookings.value = [...result]
        console.log(`\n🎉 成功！获取到 ${bookings.value.length} 条记录`)
        return
      }
      throw new Error('无法提取数据：data 为空且 result 不是数组')
    }

    // Step 5: 根据数据格式提取列表
    console.log('\n🎯 Step 5 - 智能提取列表数据:')
    
    let extractedData: any[] = []
    const dataAsAny = rawData as any  // 类型断言

    // 情况 A: 标准 RESTful 分页 { items: [...], total: N }
    if (dataAsAny.items && Array.isArray(dataAsAny.items)) {
      console.log('✓ 发现分页结构: { items: [...], total: ', dataAsAny.total, '}')
      extractedData = dataAsAny.items
      console.log('  → 使用 data.items，长度:', extractedData.length)
    }
    // 情况 B: data 本身就是数组
    else if (Array.isArray(rawData)) {
      console.log('✓ data 是直接数组')
      extractedData = rawData
      console.log('  → 使用 data，长度:', extractedData.length)
    }
    // 情况 C: 其他嵌套结构 { list: [...] } 或 { data: [...] }
    else if (typeof dataAsAny === 'object') {
      console.log('✓ data 是对象，查找可能的数组属性...')
      const possibleKeys = ['list', 'records', 'rows', 'content', 'data']
      
      for (const key of possibleKeys) {
        if (Array.isArray(dataAsAny[key])) {
          console.log(`  → 找到 data.${key} 数组`)
          extractedData = dataAsAny[key]
          break
        }
      }
      
      if (extractedData.length === 0 && Object.keys(dataAsAny).length > 0) {
        // 尝试找到任何数组属性
        const arrayKey = Object.keys(dataAsAny).find(k => Array.isArray(dataAsAny[k]))
        if (arrayKey) {
          console.log(`  → 找到 data.${arrayKey} 数组 (自动探测)`)
          extractedData = dataAsAny[arrayKey]
        } else {
          console.warn('  ⚠️ 未找到任何数组属性，keys:', Object.keys(dataAsAny))
        }
      }
    }

    // 最终检查
    console.log('\n📊 Step 6 - 提取结果统计:')
    console.log('提取的数据长度:', extractedData.length)
    
    if (extractedData.length > 0) {
      console.log('前 3 条数据预览:')
      extractedData.slice(0, 3).forEach((item: any, index: number) => {
        console.log(`  [${index}]`, JSON.stringify(item).substring(0, 200))
      })
    }

    // Step 7: 赋值给响应式变量
    console.log('\n💾 Step 7 - 更新 Vue 响应式数据:')
    
    // 强制创建新引用
    bookings.value = [...extractedData]
    
    console.log('✓ bookings.value 已更新')
    console.log('  - 新长度:', bookings.value.length)
    console.log('  - 引用地址已改变 (触发 Vue 更新)')

    // Step 8: 等待 DOM 更新
    await nextTick()
    
    console.log('\n✨ Step 8 - DOM 已更新 (nextTick 完成)')
    console.log('=' .repeat(50))
    
    // 最终状态报告
    if (bookings.value.length > 0) {
      console.log(`\n🎉🎉🎉 成功！页面应该显示 ${bookings.value.length} 条预约记录 🎉🎉🎉\n`)
    } else {
      console.warn('\n⚠️ bookings 为空数组，页面将显示"暂无预约"')
      console.warn('可能原因：1. 该用户确实没有预约记录  2. API 返回了空数据\n')
    }

  } catch (error: any) {
    console.error('\n💥 ===== 加载失败 =====')
    console.error('错误类型:', error.constructor.name)
    console.error('错误信息:', error.message || error)
    console.error('完整错误:', error)
    console.error('=' .repeat(50), '\n')
    
    uni.showToast({ 
      title: error.message?.substring(0, 20) || '加载失败', 
      icon: 'none',
      duration: 3000
    })
  }
}

const getStatusClass = (status: number | string) => {
  switch (Number(status)) {
    case BOOKING_STATUS.BOOKED: return 'booked'
    case BOOKING_STATUS.CHECKED_IN: return 'checked-in'
    case BOOKING_STATUS.COMPLETED: return 'completed'
    default: return 'cancelled'
  }
}

const getStatusText = (status: number | string) => {
  switch (Number(status)) {
    case BOOKING_STATUS.BOOKED: return '待上课'
    case BOOKING_STATUS.CHECKED_IN: return '已签到'
    case BOOKING_STATUS.COMPLETED: return '已完成'
    case BOOKING_STATUS.CANCELLED: return '已取消'
    default: return String(status)
  }
}

const handleCancel = async (bookingId: number) => {
  uni.showModal({
    title: '确认取消',
    content: '确定要取消此预约吗？',
    success: async (res) => {
      if (res.confirm) {
        try {
          const result = await bookingApi.cancel(bookingId)
          if (result.code === 0 || result.code === 200) {
            uni.showToast({ title: '取消成功', icon: 'success' })
            loadBookings()
          } else {
            uni.showToast({ title: result.msg || '取消失败', icon: 'none' })
          }
        } catch {
          uni.showToast({ title: '取消失败', icon: 'none' })
        }
      }
    }
  })
}

const goToCourses = () => {
  navigateTo({ url: '/pages/student/courses/index' })
}

// ✅ 强制刷新方法（调试用）
const forceRefresh = async () => {
  console.log('🔄 强制刷新预约列表...')
  
  // 先清空
  bookings.value = []
  await nextTick()
  
  // 重新加载
  await loadBookings()
  
  console.log('✅ 强制刷新完成，当前数据量:', bookings.value.length)
}
</script>

<style lang="scss">
.book-container {
  @include page-container;           // ✅ 使用统一的页面容器Mixin（默认$bg-primary）
}

// 主内容区域 - 统一结构
.main-content {
  @include main-content;             // ✅ 使用统一的主内容区Mixin
  padding: $space-lg $space-md $space-sm;   // 上边距增大
}

// ============================================
// 筛选标签 - 统一使用课程页面样式 (Filter Pills)
// ============================================
// 可滚动内容区域 - 自适应屏幕高度（筛选标签已提取为AppFilterTabs组件）
.booking-list {
  max-height: calc(100vh - 200rpx);       // 最大不超过屏幕减去导航栏+筛选栏
  padding-bottom: $space-md;
  padding-bottom: 180rpx;                 // 底部舒适间距
  box-sizing: border-box;
  overflow-y: auto;                       // 只在内容超出时显示滚动条

  // 空状态时禁用滚动
  &.no-scroll {
    overflow-y: hidden;                   // 隐藏滚动条
    max-height: none;                     // 移除最大高度限制
    height: auto;                         // 高度自适应内容
  }
}

.booking-list-inner {
  min-height: 100%;                       // 确保有数据时撑开
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 120rpx 0;
}

.empty-icon {
  font-size: 120rpx;
  margin-bottom: $space-md;
  opacity: 0.6;
}

.empty-text {
  font-size: $font-size-body;
  color: $text-tertiary;
  margin-bottom: $space-md;
}

.empty-btn {
  background: $primary-gradient;        // ✅ 更新：香槟金渐变
  border: none;
  border-radius: $radius-lg;          // ✅ 更新：使用圆角系统
  padding: $space-md $space-xl;
  color: #fff;
  font-size: $font-size-body;
  font-weight: $font-weight-medium;
  box-shadow: $shadow-button;          // ✅ 更新：按钮阴影

  &:active {
    transform: scale(0.96);
  }
}

.booking-card {
  background: rgba(255, 255, 255, 0.95);  // ✅ 更新：玻璃态背景
  backdrop-filter: blur(20rpx);
  -webkit-backdrop-filter: blur(20rpx);
  border-radius: $radius-lg;            // ✅ 更新：使用圆角系统
  border: 1rpx solid $border-subtle;     // ✅ 新增：浅边框
  margin-bottom: $space-md;
  overflow: hidden;
  box-shadow: $shadow-card;
  transition: transform $duration-fast $ease-standard,
              box-shadow $duration-fast $ease-standard;
  animation: cardFadeIn 0.35s cubic-bezier(0.22, 0.61, 0.36, 1) both;

  &:active {
    transform: translateY(-2rpx);
    box-shadow: $shadow-card-hover;
  }
}

.booking-status-bar {
  height: 6rpx;

  &.booked {
    background: $primary-gradient;      // ✅ 更新：香槟金渐变
  }

  &.checked-in {
    background: linear-gradient(90deg, $info-color, color.adjust($info-color, $lightness: 15%));
  }

  &.completed {
    background: linear-gradient(90deg, $success-color, color.adjust($success-color, $lightness: 10%));
  }

  &.cancelled {
    background: $bg-tertiary;
  }
}

.booking-content {
  padding: $space-md $space-lg;
}

.booking-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: $space-sm;
}

.course-name {
  font-size: $font-size-body-lg;
  font-weight: $font-weight-semibold;
  color: $text-primary;
  letter-spacing: $letter-spacing-tight;
}

.booking-status {
  font-size: $font-size-caption;
  padding: $space-2xs $space-sm;
  border-radius: $radius-full;          // ✅ 更新：使用圆角系统
  font-weight: $font-weight-medium;

  &.booked {
    background: $primary-bg;            // ✅ 更新：浅金背景
    color: $primary-solid;              // ✅ 更新：香槟金色
  }

  &.checked-in {
    background: $info-bg;               // ✅ 更新：信息背景
    color: $info-color;                 // ✅ 更新：信息颜色
  }

  &.completed {
    background: $success-bg;            // ✅ 更新：成功背景
    color: $success-color;              // ✅ 更新：成功颜色
  }

  &.cancelled {
    background: $error-bg;              // ✅ 更新：错误背景
    color: $error-color;                // ✅ 更新：错误颜色
  }
}

.booking-info {
  margin-bottom: $space-sm;
}

.booking-date {
  font-size: $font-size-body;
  color: $primary-solid;               // ✅ 更新：香槟金色
  display: block;
  margin-bottom: $space-2xs;
  font-weight: $font-weight-medium;
}

.classroom, .teacher {
  font-size: $font-size-body-sm;
  color: $text-secondary;              // ✅ 更新：使用文本变量
  display: block;
  margin-bottom: $space-2xs;
}

.booking-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: $space-sm;
  border-top: 1rpx solid $border-subtle;  // ✅ 更新：使用边框变量
}

.booking-time {
  font-size: $font-size-body-sm;
  color: $text-tertiary;
}

.booking-actions {
  display: flex;
}

.action-btn {
  padding: $space-xs $space-md;
  border-radius: $radius-xl;
  font-size: $font-size-body-sm;
  font-weight: $font-weight-medium;
  transition: background $duration-fast $ease-standard,
              color $duration-fast $ease-standard,
              transform $duration-fast $ease-standard;

  &.cancel {
    background: $error-bg;             // ✅ 更新：错误背景
    color: $error-color;               // ✅ 更新：错误颜色

    &:active {
      transform: scale(0.96);
      opacity: 0.85;
    }
  }

  &::after {
    border: none;
  }
}

.tab-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  background: rgba(255, 255, 255, 0.98);   // ✅ 更新：近白色背景
  backdrop-filter: blur(20rpx);
  -webkit-backdrop-filter: blur(20rpx);
  padding: $space-sm 0 $space-2xl;
  border-top: 1rpx solid $border-light;     // ✅ 更新：使用边框变量
  box-shadow: 0 -4rpx 16rpx rgba(26, 26, 26, 0.04);
}

@keyframes cardFadeIn {
  from {
    opacity: 0;
    transform: translateY(8rpx);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.tab-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;

  &.active {
    .tab-icon, .tab-text {
      color: $primary-solid;            // ✅ 更新：香槟金色
    }
  }
}

.tab-icon {
  font-size: $icon-size-md;
  margin-bottom: $space-2xs;
  color: $text-tertiary;
  transition: color $duration-fast $ease-standard;
}

.tab-text {
  font-size: $font-size-caption;
  color: $text-tertiary;
  transition: color $duration-fast $ease-standard;
}
</style>