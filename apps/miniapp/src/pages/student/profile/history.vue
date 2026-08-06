<template>
  <view class="history-container">
    <!-- 筛选标签 - 使用统一组件 -->
    <AppFilterTabs
      v-model="activeFilter"
      :tabs="filterTabs"
      @change="filterHistory"
    />

    <scroll-view scroll-y class="history-list" :style="{ height: scrollHeight + 'px' }" :show-scrollbar="false">
      <view v-if="filteredHistory.length > 0" class="history-list-inner">
        <view
          v-for="(record, index) in filteredHistory"
          :key="record.id || index"
          class="history-card"
          :class="getStatusClass(record.status)"
        >
          <view class="history-header">
            <text class="course-name">{{ record.course_name || '未知课程' }}</text>
            <view class="status-badge" :class="'status-' + record.status">
              {{ getStatusText(record.status) }}
            </view>
          </view>

          <view class="history-info">
            <view class="info-item">
              <text class="info-icon">📅</text>
              <text class="info-text">{{ formatDate(record.start_at) }} {{ formatTime(record.start_at) }}</text>
            </view>
            <view class="info-item">
              <text class="info-icon">🕐</text>
              <text class="info-text">{{ formatTime(record.start_at) }} - {{ formatTime(record.end_at) }}</text>
            </view>
            <view class="info-item">
              <text class="info-icon">📍</text>
              <text class="info-text">{{ record.classroom_name || '未安排教室' }}</text>
            </view>
            <view class="info-item">
              <text class="info-icon">👨‍🏫</text>
              <text class="info-text">{{ record.teacher_name || '未知' }}</text>
            </view>
          </view>

          <view class="history-footer">
            <text class="booking-time">预约时间: {{ formatDateTime(record.created_at) }}</text>
            <text v-if="record.cancel_reason" class="cancel-reason">取消原因: {{ record.cancel_reason }}</text>
          </view>
        </view>
      </view>

      <view v-else class="empty-state">
        <text class="empty-icon">📋</text>
        <text class="empty-text">暂无{{ getCurrentFilterLabel() }}记录</text>
      </view>
    </scroll-view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { bookingApi } from '@/api'
import { checkLogin } from '@/utils/auth'
import { extractList } from '@/utils/helpers'
import { formatDateTime, formatDate, formatTime } from '@/utils/date'
import AppFilterTabs from '@/components/AppFilterTabs.vue'

const allHistory = ref<any[]>([])
const filteredHistory = computed(() => {
  if (activeFilter.value === 'all') {
    return allHistory.value
  }

  return allHistory.value.filter((record: any) => {
    const status = String(record.status || '').toLowerCase()

    switch (activeFilter.value) {
      case 'completed':
        return status === 'completed' || status === '3' || status === '已完成'
      case 'cancelled':
        return status === 'cancelled' || status === '4' || status === '已取消'
      case 'no_show':
        return status === 'no_show' || status === '5' || status === '缺课'
      default:
        return true
    }
  })
})

const activeFilter = ref('all')
const scrollHeight = ref(600)

const filterTabs = [
  { label: '全部', value: 'all' },
  { label: '已完成', value: 'completed' },
  { label: '已取消', value: 'cancelled' },
  { label: '缺课', value: 'no_show' }
]

onMounted(() => {
  console.log('\n📋 ===== 历史记录页面 - onMounted 触发 =====\n')

  if (!checkLogin('student')) {
    console.warn('⚠️ 用户未登录或角色不匹配')
    uni.showToast({ title: '请先登录', icon: 'none' })
    setTimeout(() => {
      uni.navigateBack()
    }, 1500)
    return
  }

  calculateScrollHeight()
  loadHistory()
})

const calculateScrollHeight = () => {
  const systemInfo = uni.getSystemInfoSync()
  const windowHeight = systemInfo.windowHeight
  const otherHeight = 250
  scrollHeight.value = Math.max(windowHeight - otherHeight, 400)
}

const loadHistory = async () => {
  try {
    console.log('\n🔍 ===== 开始加载历史记录 =====')

    // ✅ 关键修复：传入状态参数，只获取历史记录（已完成/已取消/缺课）
    // 注意：根据后端实际支持的参数格式调整
    const result = await bookingApi.list({ 
      status: 'completed,cancelled,no_show'  // 方案1：逗号分隔的字符串
      // 或者尝试数字格式（取决于后端实现）：
      // status: '3,4,5'  // 3=已完成, 4=已取消, 5=缺课
    })
    console.log('✅ API 返回:', result)
    console.log('📝 请求参数: status=completed,cancelled,no_show (仅历史记录)')

    const responseData = result?.data as any
    let list: any[] = []

    if (responseData?.items && Array.isArray(responseData.items)) {
      list = responseData.items
      console.log('✅ 使用 data.items，总数:', list.length)
    } else if (Array.isArray(responseData)) {
      list = responseData
      console.log('✅ 使用 data（直接数组），总数:', list.length)
    } else {
      list = extractList(result)
      console.log('⚠️ 使用 extractList 兜底，总数:', list.length)
    }

    allHistory.value = [...list]

    console.log('\n📊 历史记录统计:')
    console.log('- 总数:', allHistory.value.length)
    console.log('- 已完成:', allHistory.value.filter((r: any) => {
      const s = String(r.status || '').toLowerCase()
      return s === 'completed' || s === '3' || s === '已完成'
    }).length)
    console.log('- 已取消:', allHistory.value.filter((r: any) => {
      const s = String(r.status || '').toLowerCase()
      return s === 'cancelled' || s === '4' || s === '已取消'
    }).length)
    console.log('- 缺课:', allHistory.value.filter((r: any) => {
      const s = String(r.status || '').toLowerCase()
      return s === 'no_show' || s === '5' || s === '缺课'
    }).length)

    console.log('\n✅✅✅ 历史记录加载完成！（仅包含已完成/已取消/缺课的记录）')

  } catch (error: any) {
    console.error('❌ 加载历史记录失败:', error)
    
    // 如果后端不支持status参数，降级为全量获取+前端过滤
    console.warn('⚠️ 可能后端不支持status参数，尝试降级方案...')
    
    try {
      const fallbackResult = await bookingApi.list({})
      const fallbackData = fallbackResult?.data as any
      let fallbackList: any[] = []
      
      if (fallbackData?.items && Array.isArray(fallbackData.items)) {
        fallbackList = fallbackData.items
      } else if (Array.isArray(fallbackData)) {
        fallbackList = fallbackData
      } else {
        fallbackList = extractList(fallbackResult)
      }
      
      // ✅ 前端过滤：只保留历史状态
      allHistory.value = fallbackList.filter((record: any) => {
        const s = String(record.status || '').toLowerCase()
        return ['completed', '3', '已完成', 
                'cancelled', '4', '已取消', 
                'no_show', '5', '缺课'].includes(s)
      })
      
      console.log('✅ 降级成功：使用前端过滤，获取', allHistory.value.length, '条历史记录')
      
    } catch (fallbackError) {
      console.error('❌ 降级方案也失败:', fallbackError)
      uni.showToast({
        title: error.message?.substring(0, 20) || '加载失败',
        icon: 'none',
        duration: 3000
      })
    }
  }
}

const filterHistory = () => {
  console.log('\n🔄 切换筛选条件:', activeFilter.value)
}

const getStatusText = (status: any): string => {
  const s = String(status || '').toLowerCase()

  if (s === 'booked' || s === '1' || s === '已预约') return '已预约'
  if (s === 'checked_in' || s === '2' || s === '已签到') return '已签到'
  if (s === 'completed' || s === '3' || s === '已完成') return '已完成'
  if (s === 'cancelled' || s === '4' || s === '已取消') return '已取消'
  if (s === 'no_show' || s === '5' || s === '缺课') return '缺课'

  return '未知状态'
}

const getStatusClass = (status: any): string => {
  const s = String(status || '').toLowerCase()

  if (s === 'completed' || s === '3' || s === '已完成') return 'status-completed'
  if (s === 'cancelled' || s === '4' || s === '已取消') return 'status-cancelled'
  if (s === 'no_show' || s === '5' || s === '缺课') return 'status-no-show'
  if (s === 'checked_in' || s === '2' || s === '已签到') return 'status-checked-in'

  return ''
}

const getCurrentFilterLabel = (): string => {
  const tab = filterTabs.find(t => t.value === activeFilter.value)
  return tab ? tab.label : ''
}
</script>

<style lang="scss">
// 页面中央标题
.page-title {
  font-size: 32rpx;
  font-weight: $font-weight-medium;
  color: $text-primary;
  line-height: 1.4;
}

.history-container {
  padding: $space-lg $space-md $space-sm;   // 上边距增大
  min-height: 100vh;
  background: $bg-primary;                    // ✅ 使用Design System变量
}

// ============================================
// 筛选标签 - 统一使用课程页面样式 (Filter Pills)
// ============================================
// 历史记录列表（筛选标签已提取为AppFilterTabs组件）
.history-list {
  padding: $space-md $space-lg;
  padding-bottom: 100rpx;                // 底部留白
  box-sizing: border-box;
}

.history-list-inner {
  min-height: 100%;
}

// ✨ 卡片设计 - 高级轻奢风格
.history-card {
  background: $card-background;          // ✅ 卡片背景
  border-radius: $radius-lg;            // ✅ 大圆角
  padding: $space-lg;
  margin-bottom: $space-md;
  box-shadow: $shadow-card;              // ✅ 卡片阴影
  border-left: 8rpx solid transparent;
  transition: all $duration-fast $ease-elegant;

  &:active {
    transform: scale(0.98);
    box-shadow: $shadow-card-hover;      // ✅ 悬停阴影
  }

  // 状态颜色 - 保持语义化但使用更柔和的色调
  &.status-completed {
    border-left-color: $success-color;   // ✅ 成功绿 (#7CB986)
  }

  &.status-cancelled {
    border-left-color: $error-color;     // ✅ 错误红 (#D4847A)
    opacity: 0.75;
  }

  &.status-no-show {
    border-left-color: $warning-color;   // ✅ 警告黄 (#D4A76A)
    opacity: 0.75;
  }

  &.status-checked-in {
    border-left-color: $info-color;      // ✅ 信息蓝 (#8BA4B8)
  }
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: $space-md;
}

.course-name {
  font-size: $font-size-h3;              // ✅ 三级标题（32rpx）
  font-weight: $font-weight-semibold;   // ✅ 半粗体
  color: $text-primary;                 // ✅ 主文字色
  flex: 1;
}

// 状态徽章 - 更精致的胶囊设计
.status-badge {
  padding: $space-xs $space-sm;
  border-radius: $radius-full;
  font-size: $font-size-overline;       // ✅ 标签/角标（22rpx）
  font-weight: $font-weight-medium;
  margin-left: $space-sm;

  // 各状态配色 - 使用 Design System 语义色
  &.status-booked,
  &.status-1 {
    background: $info-bg;               // ✅ 预定义的10%透明度背景
    color: $info-color;                 // ✅ 信息蓝 (#8BA4B8)
  }

  &.status-checked-in,
  &.status-2 {
    background: rgba($primary-solid, 0.08);
    color: $primary-solid;             // ✅ 品牌主色（香槟金）
  }

  &.status-completed,
  &.status-3 {
    background: $success-bg;           // ✅ 预定义的12%透明度背景
    color: $success-color;             // ✅ 成功绿 (#7CB986)
  }

  &.status-cancelled,
  &.status-4 {
    background: $error-bg;             // ✅ 预定义的12%透明度背景
    color: $error-color;               // ✅ 错误红 (#D4847A)
  }

  &.status-no-show,
  &.status-5 {
    background: $warning-bg;           // ✅ 预定义的12%透明度背景
    color: $warning-color;             // ✅ 警告黄 (#D4A76A)
  }
}

.history-info {
  display: flex;
  flex-direction: column;
  gap: $space-sm;
  margin-bottom: $space-md;
}

.info-item {
  display: flex;
  align-items: center;
  gap: $space-sm;
}

.info-icon {
  font-size: $font-size-body;           // ✅ 正文标准（28rpx）
  width: 36rpx;
  text-align: center;
  opacity: 0.8;
}

.info-text {
  font-size: $font-size-body;           // ✅ 正文标准（28rpx）
  color: $text-secondary;               // ✅ 次要文字色
}

.history-footer {
  padding-top: $space-sm;
  border-top: 1rpx solid $border-subtle; // ✅ 微弱分割线
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.booking-time,
.cancel-reason {
  font-size: $font-size-overline;       // ✅ 标签/角标（22rpx）
  color: $text-tertiary;                // ✅ 三级文字色
}

.cancel-reason {
  color: $error-color;                 // ✅ 错误红 (#D4847A)
}

// 空状态设计 - 更优雅的展示
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: $space-3xl $space-lg;
}

.empty-icon {
  font-size: 96rpx;                    // ✅ 更大的图标
  margin-bottom: $space-md;
  opacity: 0.6;
}

.empty-text {
  font-size: $font-size-body;           // ✅ 正文标准（28rpx）
  color: $text-tertiary;               // ✅ 柔和的文字
}
</style>