<template>
  <view class="schedule-container">
    <!-- 自定义导航栏 - 统一使用AppNavbar -->
    <AppNavbar
      title=""
      :show-back="false"
      variant="default"
    >
      <template #left>
        <view>排期列表</view>
      </template>
    </AppNavbar>

    <!-- 主内容区域 - 参照课程页面结构 -->
    <view class="main-content">
      <!-- 日期选择器 -->
      <view class="box-selector">
        <view class="date-selector">
          <view class="date-btn" @tap="prevWeek">
            <text>←</text>
          </view>
          <text class="date-range">{{ dateRangeText }}</text>
          <view class="date-btn" @tap="nextWeek">
            <text>→</text>
          </view>
        </view>

        <!-- 星期头部 -->
        <view class="week-header">
          <view v-for="day in weekDays" :key="day.date" class="day-item" @tap="selectDate(day.date)">
            <text class="day-name">{{ day.name }}</text>
            <text class="day-date" :class="{ today: day.isToday, selected: selectedDate === day.date }">{{ day.day }}</text>
          </view>
        </view>
      </view>

    <scroll-view scroll-y class="schedule-scroll" :style="{ height: scrollViewHeight + 'px' }" :show-scrollbar="false">
      <view v-if="loading" class="loading-state">
        <text class="loading-text">加载中...</text>
      </view>
      <view v-else-if="daySchedules.length === 0" class="empty-state">
        <text class="empty-icon">📅</text>
        <text class="empty-text">暂无排期</text>
      </view>

      <view
        v-else
        v-for="(schedule, index) in displaySchedules"
        :key="schedule._key"
        class="schedule-card"
        :style="{ animationDelay: `${index * 0.04}s` }"
      >
        <view class="schedule-time">
          <text class="time-start">{{ schedule._startTime }}</text>
          <view class="time-line"></view>
          <text class="time-end">{{ schedule._endTime }}</text>
        </view>

        <view class="schedule-content">
          <view class="schedule-header">
            <text class="course-name">{{ schedule.course_name || '未知课程' }}</text>
            <view class="booking-badge" :class="schedule._statusClass">
              <text>{{ schedule._statusText }}</text>
            </view>
          </view>
          <view class="schedule-info">
            <text class="classroom">📍 {{ schedule.classroom_name || '未安排教室' }}</text>
            <text class="teacher">👨‍🏫 {{ schedule.teacher_name || '未知' }}</text>
          </view>
          <view class="schedule-footer">
            <text class="count">{{ schedule.booked_count }}/{{ schedule.capacity }}人</text>
            <button
              class="book-btn"
              :class="{
                disabled: schedule._isDisabled,
                booked: schedule._isBooked
              }"
              :disabled="schedule._isDisabled"
              @tap="handleBooking(schedule.id)"
            >
              {{ schedule._btnText }}
            </button>
          </view>
        </view>
      </view>
    </scroll-view>

    </view><!-- /main-content -->

    <StudentTabBar currentRoute="/pages/student/schedule/index" />

    <!-- AI 智能助手 -->
    <AiAssistant
      :session-id="'student_' + (userId || 'default')"
    />
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watchEffect } from 'vue'
import { scheduleApi, bookingApi } from '@/api'
import { checkLogin } from '@/utils/auth'
import { formatTime, formatDate, toAPIDateTime, isScheduleExpired, isWithinBookingWindow } from '@/utils/date'
import StudentTabBar from '@/components/StudentTabBar.vue'
import AiAssistant from '@/components/AiAssistant.vue'
import AppNavbar from '@/components/AppNavbar.vue'
import { extractList } from '@/utils/helpers'

const currentWeekStart = ref('')
const selectedDate = ref('')
const daySchedules = ref<any[]>([])
const bookings = ref<any[]>([])
const loading = ref(false)
const userId = ref('')

const systemInfo = uni.getSystemInfoSync()
const navbarHeight = systemInfo.statusBarHeight + 44
const tabbarHeight = (100 / 750) * systemInfo.windowWidth
const scrollViewHeight = ref(Math.max(
  systemInfo.windowHeight - navbarHeight - tabbarHeight - 160,
  400
))

// ✅ 防重复调用锁
let isLoadingSchedules = false
let isLoadingBookings = false

// ✅ 防抖定时器
let debounceTimer: number | null = null

// ✅ 保存watchEffect的stop函数
let stopWatcher: (() => void) | null = null

let loadBookingsTimer: number | null = null
let retryTimer: number | null = null

// ✅ 页面卸载标记（防止异步回调更新已销毁的页面）
let isUnmounted = false

// ✅ 企业级优化：Computed预处理所有显示数据（性能关键！）
const displaySchedules = computed(() => {
  const bookedScheduleIds = new Set(
    bookings.value.map((b: any) => b.schedule_id)
  )
  
  return daySchedules.value.map((schedule: any, index: number) => {
    const isBooked = bookedScheduleIds.has(schedule.id)
    const isFull = schedule.booked_count >= schedule.capacity
    const isExpired = isScheduleExpired(schedule.start_at)
    const isOutOfWindow = !isWithinBookingWindow(schedule.start_at, 14)
    
    const isDisabled = isExpired || isOutOfWindow || (isFull && !isBooked)
    
    let statusText: string
    let btnText: string
    let statusClass: string
    
    if (isBooked) {
      statusText = '已预约'
      btnText = '取消'
      statusClass = 'booked'
    } else if (isExpired) {
      statusText = '已过期'
      btnText = '已过期'
      statusClass = 'expired'
    } else if (isOutOfWindow) {
      statusText = '超出范围'
      btnText = '不可预约'
      statusClass = 'expired'
    } else if (isFull) {
      statusText = '已满'
      btnText = '已满'
      statusClass = 'full'
    } else {
      statusText = '可预约'
      btnText = '预约'
      statusClass = 'available'
    }
    
    return {
      ...schedule,
      _key: schedule.id || `schedule-${selectedDate.value}-${index}`,
      _startTime: formatTime(schedule.start_at),
      _endTime: formatTime(schedule.end_at),
      _isBooked: isBooked,
      _isFull: isFull,
      _isDisabled: isDisabled,
      _statusClass: statusClass,
      _statusText: statusText,
      _btnText: btnText
    }
  })
})

const weekDays = computed(() => {
  const days = []
  const dayNames = ['日', '一', '二', '三', '四', '五', '六']
  const today = new Date()
  const startDate = currentWeekStart.value ? new Date(currentWeekStart.value) : getWeekStart(today)
  
  for (let i = 0; i < 7; i++) {
    const date = new Date(startDate)
    date.setDate(startDate.getDate() + i)
    const dateStr = date.toISOString().split('T')[0]
    days.push({
      date: dateStr,
      name: dayNames[date.getDay()],
      day: date.getDate(),
      isToday: dateStr === today.toISOString().split('T')[0]
    })
  }
  return days
})

const dateRangeText = computed(() => {
  if (weekDays.value.length >= 2) {
    const startDate = weekDays.value[0].date
    const endDate = weekDays.value[6].date
    // ✅ 使用 formatDate 显示友好格式（如：1月15日 ~ 1月21日）
    return `${formatDate(startDate)} ~ ${formatDate(endDate)}`
  }
  return ''
})

function getWeekStart(date: Date): Date {
  const d = new Date(date)
  const day = d.getDay()
  const diff = d.getDate() - day + (day === 0 ? -6 : 1)
  return new Date(d.setDate(diff))
}

onMounted(() => {
  if (!checkLogin('student')) return

  const userInfo = uni.getStorageSync('user_info')
  if (userInfo) {
    try {
      const parsed = JSON.parse(userInfo)
      userId.value = parsed.id || ''
    } catch {}
  }

  const today = new Date().toISOString().split('T')[0]
  selectedDate.value = today
  loadSchedules()

  // ✅ 状态监控（调试用，可在生产环境删除）
  stopWatcher = watchEffect(() => {
    console.log('🔍 [State Watcher]', {
      timestamp: new Date().toLocaleTimeString(),
      loading: loading.value,
      isLoadingSchedules: isLoadingSchedules,
      isLoadingBookings: isLoadingBookings,
      daySchedules_length: daySchedules.value.length,
      bookings_length: bookings.value.length,
      selectedDate: selectedDate.value
    })
  })
})
onUnmounted(() => {
  isUnmounted = true
  if (stopWatcher) {
    stopWatcher()
    stopWatcher = null
  }
  if (debounceTimer) {
    clearTimeout(debounceTimer)
    debounceTimer = null
  }
  if (loadBookingsTimer) {
    clearTimeout(loadBookingsTimer)
    loadBookingsTimer = null
  }
  if (retryTimer) {
    clearTimeout(retryTimer)
    retryTimer = null
  }
})

const loadSchedules = async () => {
  // ✅ 改进：如果正在加载中，不再直接跳过，而是等待当前请求完成后自动用最新日期重试
  if (isLoadingSchedules) {
    console.warn('⚠️ [Schedule] loadSchedules 正在执行，将使用最新日期:', selectedDate.value)
    // 不return，让当前请求继续，但标记需要重试
    pendingDateRefresh = selectedDate.value
    return
  }

  // ✅ 加锁
  isLoadingSchedules = true
  loading.value = true
  
  try {
    const apiDateTime = toAPIDateTime(selectedDate.value)

    console.log('=== 📅 排期页面 - 加载排期数据 ===')
    console.log('选中日期:', selectedDate.value)
    console.log('API 时间参数:', apiDateTime)

    const result = await scheduleApi.list({
      start_from: apiDateTime.start,
      start_to: apiDateTime.end,
      status: 1
    })

    // ✅ 页面已卸载，不再更新数据
    if (isUnmounted) return

    console.log('=== 排期列表 - API 返回 ===')
    console.log('result.data:', result?.data)

    const responseData = result?.data as any

    let finalList: any[] = []

    if (responseData?.items && Array.isArray(responseData.items)) {
      finalList = responseData.items
      console.log('✅ 使用 data.items，长度:', finalList.length)
    } else if (Array.isArray(responseData)) {
      finalList = responseData
      console.log('✅ 使用 data（直接数组），长度:', finalList.length)
    } else {
      finalList = extractList(result)
      console.log('⚠️ 使用 extractList 兜底，长度:', finalList.length)
    }

    if (finalList.length > 0) {
      console.log('\n📋 前 2 条排期的日期字段:')
      finalList.slice(0, 2).forEach((schedule: any, index: number) => {
        console.log(`[${index}] ${schedule.course_name || '未知'}:`)
        console.log('  - start_at:', schedule.start_at, '→ 格式化后:', formatTime(schedule.start_at))
        console.log('  - end_at:', schedule.end_at, '→ 格式化后:', formatTime(schedule.end_at))
      })
    }

    // ✅✅✅ 关键修复：先赋值排期数据
    daySchedules.value = finalList
    
    // ✅✅✅ 关键修复：立即设置loading=false，让列表立刻显示！
    loading.value = false
    
    console.log('\n✅ 排期列表 - 已加载:', daySchedules.value.length, '条排期')
    console.log('✅ [Schedule] loading已设置为false，列表应该立即可见')

    // ✅ 等待Vue完成渲染（确保列表已显示）
    await nextTick()

    console.log('🎯 [Schedule] DOM更新完成，准备加载预约数据...')

    // ✅ 延迟加载预约数据（后台静默更新按钮状态）
    loadBookingsTimer = setTimeout(() => {
      loadBookings()
      loadBookingsTimer = null
    }, 150) as unknown as number

  } catch (error) {
    console.error('❌ 排期列表 - 加载失败:', error)
    uni.showToast({ title: '加载失败', icon: 'none' })
    
    // ✅ 出错时也要确保解锁和停止loading
    isLoadingSchedules = false
    loading.value = false
  }
}

// ✅ 新增：待处理的日期刷新请求
let pendingDateRefresh: string | null = null

// ✅ 新增：完成加载的回调函数（由loadBookings调用）
const onAllDataLoaded = () => {
  isLoadingSchedules = false  // 只解锁，不再控制loading（loading已在loadSchedules中设置）
  
  console.log('✅ [Schedule] 预约数据加载完成')
  
  // ✅ 检查是否有待处理的日期刷新请求
  if (pendingDateRefresh && pendingDateRefresh !== selectedDate.value) {
    console.log('🔄 [Schedule] 检测到待处理请求，自动刷新至日期:', pendingDateRefresh)
    const refreshDate = pendingDateRefresh
    pendingDateRefresh = null  // 清除标记
    
    // 延迟一小段时间再执行，确保状态完全重置
    retryTimer = setTimeout(() => {
      loadSchedules()
      retryTimer = null
    }, 50) as unknown as number
    return
  }
  
  console.log('✅ [Schedule] 所有操作完成')
}

const loadBookings = async () => {
  // ✅ 防重复调用：如果正在加载中，跳过
  if (isLoadingBookings) {
    console.warn('⚠️ [Booking] loadBookings 正在执行，跳过重复调用')
    return
  }

  // ✅ 加锁
  isLoadingBookings = true

  try {
    console.log('=== 🎫 排期页面 - 加载预约数据 ===')
    console.log('请求参数:', { status: 1 })

    const result = await bookingApi.list({ status: 1 })  // 1=已预约

    // ✅ 页面已卸载，不再更新数据
    if (isUnmounted) return

    console.log('📦 [Booking] API 返回:', result)
    console.log('📦 [Booking] result.data:', result?.data)

    const responseData = result?.data as any

    let finalList: any[] = []

    if (responseData?.items && Array.isArray(responseData.items)) {
      console.log('✅ [Booking] 使用 result.data.items')
      finalList = responseData.items
    } else if (Array.isArray(responseData)) {
      console.log('✅ [Booking] 使用 result.data (直接数组)')
      finalList = responseData
    } else {
      console.log('⚠️ [Booking] 使用 extractList 兜底')
      finalList = extractList(result)
    }

    console.log('📊 [Booking] 最终列表长度:', finalList.length)

    // ✅ 直接赋值（不使用展开运算符，减少内存开销）
    bookings.value = finalList

    console.log('✅ [Booking] bookings.value 长度:', bookings.value.length)

    // ✅ 验证最终状态
    console.log('\n🔍 [Final State Check]')
    console.log('  - loading:', loading.value)
    console.log('  - daySchedules.length:', daySchedules.value.length)
    console.log('  - bookings.length:', bookings.value.length)
    
    if (daySchedules.value.length === 0) {
      console.warn('⚠️ [Warning] daySchedules 为空！这可能是数据消失的原因')
    }
    
  } catch (error) {
    console.error('❌ [Booking] 加载预约失败:', error)
    
    // ✅ 不要让错误影响已显示的列表
    // 不重置任何状态，只提示用户（可选）
    // uni.showToast({ title: '预约信息加载失败', icon: 'none' })
    
  } finally {
    // ✅ 解锁
    isLoadingBookings = false
    
    // ✅ 通知loadSchedules：所有数据已加载完成
    onAllDataLoaded()
  }
}

const prevWeek = () => {
  const start = new Date(currentWeekStart.value || new Date())
  const todayWeekStart = getWeekStart(new Date())
  const newStart = new Date(start)
  newStart.setDate(start.getDate() - 7)
  
  if (newStart.getTime() < todayWeekStart.getTime()) {
    uni.showToast({ title: '无法查看更早的课程', icon: 'none' })
    return
  }
  currentWeekStart.value = newStart.toISOString().split('T')[0]
}

const nextWeek = () => {
  const start = new Date(currentWeekStart.value || new Date())
  const todayWeekStart = getWeekStart(new Date())
  const maxWeekStart = new Date(todayWeekStart)
  maxWeekStart.setDate(todayWeekStart.getDate() + 14)
  
  const newStart = new Date(start)
  newStart.setDate(start.getDate() + 7)
  
  if (newStart.getTime() > maxWeekStart.getTime()) {
    uni.showToast({ title: '仅可预约两周内的课程', icon: 'none' })
    return
  }
  currentWeekStart.value = newStart.toISOString().split('T')[0]
}

const selectDate = (date: string) => {
  // ✅ 如果点击的是已选中的日期，不重复加载
  if (date === selectedDate.value) {
    console.log('📅 [Date] 点击相同日期，跳过')
    return
  }

  console.log('📅 [Date] 切换日期:', selectedDate.value, '→', date)
  selectedDate.value = date

  // ✅ 防抖：清除之前的定时器
  if (debounceTimer) {
    clearTimeout(debounceTimer)
  }

  // ✅ 使用全局setTimeout（微信小程序没有window对象）
  debounceTimer = setTimeout(() => {
    loadSchedules()
    debounceTimer = null
  }, 100) as unknown as number
}

// ✅ 已删除冗余函数（已被displaySchedules computed替代）：
// - hasBooking() → 使用 displaySchedules[i]._isBooked
// - getBookingStatusClass() → 使用 displaySchedules[i]._statusClass
// - getBookingStatusText() → 使用 displaySchedules[i]._statusText

// ✅ 辅助函数：快速判断是否已预约（仅用于事件处理，不用于模板渲染）
const isScheduleBooked = (scheduleId: number): boolean => {
  return bookings.value.some((booking: any) => booking.schedule_id === scheduleId)
}

const handleBooking = async (scheduleId: number) => {
  const schedule = daySchedules.value.find((s: any) => s.id === scheduleId)
  if (!schedule) {
    uni.showToast({ title: '排期不存在', icon: 'none' })
    return
  }

  if (isScheduleExpired(schedule.start_at)) {
    uni.showToast({ title: '该课程已过期，无法预约', icon: 'none' })
    return
  }

  if (!isWithinBookingWindow(schedule.start_at, 14)) {
    uni.showToast({ title: '仅可预约两周内的课程', icon: 'none' })
    return
  }

  if (isScheduleBooked(scheduleId)) {
    uni.showModal({
      title: '取消预约',
      content: '确定要取消此预约吗？',
      success: async (res) => {
        if (res.confirm) {
          await cancelBooking(scheduleId)
        }
      }
    })
    return
  }

  uni.showModal({
    title: '确认预约',
    content: '确定要预约此课程吗？',
    success: async (res) => {
      if (res.confirm) {
        try {
          const result = await bookingApi.create({ schedule_id: scheduleId })
          if (result.code === 0 || result.code === 200) {
            uni.showToast({ title: '预约成功', icon: 'success' })
            await Promise.all([loadSchedules(), loadBookings()])
          } else {
            uni.showToast({ title: result.msg || '预约失败', icon: 'none' })
          }
        } catch {
          uni.showToast({ title: '预约失败', icon: 'none' })
        }
      }
    }
  })
}

const cancelBooking = async (scheduleId: number) => {
  try {
    const booking = bookings.value.find((b: any) => b.schedule_id === scheduleId)
    if (!booking) {
      uni.showToast({ title: '未找到预约记录', icon: 'none' })
      return
    }

    const result = await bookingApi.cancel(booking.id)
    if (result.code === 0 || result.code === 200) {
      uni.showToast({ title: '取消成功', icon: 'success' })
      await Promise.all([loadSchedules(), loadBookings()])
    } else {
      uni.showToast({ title: result.msg || '取消失败', icon: 'none' })
    }
  } catch {
    uni.showToast({ title: '取消失败', icon: 'none' })
  }
}
</script>

<style lang="scss">
.schedule-container {
  @include page-container;
  overflow: visible;                     // ✅ iOS兼容：覆盖full-screen的overflow:hidden
}

// 主内容区域 - 统一结构
.main-content {
  @include main-content;
  overflow: visible;                     // ✅ iOS兼容：移除overflow:hidden避免裁剪scroll-view内容
  padding: $space-lg $space-md $space-sm;
}
.box-selector {
  border-radius: $radius-lg;
  background: rgba(255, 255, 255, 0.95);
}

.date-selector {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: $space-lg $space-lg $space-md;   // ✅ 增加顶部安全间距（与导航栏保持距离）
  border-bottom: 1rpx solid $border-light;
  flex-shrink: 0;
}

.date-btn {
  width: 64rpx;
  height: 64rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: $bg-tertiary;               // ✅ 更新：使用三级背景
  border-radius: $radius-full;
  font-size: $font-size-body;
  color: $text-primary;
  transition: background $duration-fast $ease-standard,
              transform $duration-fast $ease-standard;

  &:active {
    background: $primary-bg;
    transform: scale(0.95);
  }
}

.date-range {
  font-size: $font-size-body;
  color: $text-primary;
  font-weight: $font-weight-medium;
}

.week-header {
  display: flex;
  padding: $space-sm 0;
  border-bottom: 1rpx solid $border-subtle;
  flex-shrink: 0;
}

.day-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.day-name {
  font-size: $font-size-caption;
  color: $text-tertiary;
  margin-bottom: $space-2xs;
}

.day-date {
  width: 56rpx;
  height: 56rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: $radius-full;
  font-size: $font-size-body-sm;
  transition: background $duration-fast $ease-standard,
              color $duration-fast $ease-standard,
              box-shadow $duration-fast $ease-standard,
              font-weight $duration-fast $ease-standard;

  &.today {
    background: $primary-solid;           // ✅ 更新：香槟金色
    color: #fff;
    box-shadow: $glow-primary;            // ✅ 更新：光晕效果
  }

  &.selected {
    background: $primary-bg;             // ✅ 更新：浅金背景
    color: $primary-solid;
    font-weight: $font-weight-semibold;
  }
}

.schedule-scroll {
  padding: $space-md 0;
  padding-bottom: 180rpx;
  box-sizing: border-box;
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 120rpx 0;
}

.loading-text,
.empty-text {
  font-size: $font-size-body;
  color: $text-tertiary;
}

.empty-icon {
  font-size: 120rpx;
  margin-bottom: $space-md;
  opacity: 0.6;
}

.schedule-card {
  display: flex;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20rpx);
  -webkit-backdrop-filter: blur(20rpx);
  border-radius: $radius-lg;
  border: 1rpx solid $border-subtle;
  padding: $space-md $space-lg;
  margin-bottom: $space-md;
  box-shadow: $shadow-card;
  transition: transform $duration-fast $ease-standard,
              box-shadow $duration-fast $ease-standard;
  animation: cardFadeIn 0.35s cubic-bezier(0.22, 0.61, 0.36, 1) both;

  &:active {
    transform: translateY(-2rpx);
    box-shadow: $shadow-card-hover;
  }
}

.schedule-time {
  width: 100rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-right: $space-md;
}

.time-start, .time-end {
  font-size: $font-size-caption;
  font-weight: $font-weight-semibold;
  color: $primary-solid;                  // ✅ 更新：香槟金色
}

.time-line {
  width: 2rpx;
  height: 40rpx;
  background: $border-light;       // ✅ 更新：使用边框变量
  margin: $space-2xs 0;
  border-radius: $radius-full;
}

.schedule-content {
  flex: 1;
}

.schedule-header {
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

.booking-badge {
  padding: $space-2xs $space-sm;
  border-radius: $radius-full;
  font-size: $font-size-caption;
  font-weight: $font-weight-medium;

  &.booked {
    background: $primary-bg;        // ✅ 更新：浅金背景
    color: $primary-solid;          // ✅ 更新：香槟金色
  }

  &.full {
    background: $error-bg;          // ✅ 更新：错误背景
    color: $error-color;            // ✅ 更新：错误颜色
  }

  &.available {
    background: $success-bg;
    color: $success-color;
  }

  &.expired {
    background: $bg-tertiary;
    color: $text-tertiary;
  }
}

.schedule-info {
  margin-bottom: $space-sm;
}

.classroom, .teacher {
  font-size: $font-size-body-sm;
  color: $text-secondary;
  display: block;
  margin-bottom: $space-2xs;
}

.schedule-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: $space-md;
}

.count {
  font-size: $font-size-body-sm;
  color: $text-tertiary;
  order: -1;
  margin-right: auto;
}

.book-btn {
  padding: $space-xs $space-lg;
  background: $primary-gradient;   // ✅ 更新：香槟金渐变
  color: #fff;
  border-radius: $radius-2xl;     // ✅ 更新：使用圆角系统
  border: none;
  font-size: $font-size-body-sm;
  font-weight: $font-weight-medium;
  letter-spacing: $letter-spacing-tight;
  transition: background $duration-fast $ease-standard,
              transform $duration-fast $ease-standard,
              box-shadow $duration-fast $ease-standard,
              opacity $duration-fast $ease-standard;
  box-shadow: $shadow-button;

  &::after {
    border: none;
  }

  &:active {
    transform: scale(0.96);
    box-shadow: $shadow-button-hover;
  }

  &.disabled {
    background: $bg-tertiary;
    color: $text-disabled;
    box-shadow: none;

    &::after {
      border: none;
    }

    &.booked {
      background: $accent-solid;  // ✅ 更新：莫兰迪粉
      color: #fff;
      opacity: 0.75;

      &::after {
        border: none;              // 禁用+已预约状态也去除边框
      }
    }
  }

  &.booked {
    background-color: #e53935;     // ✅ 鲜艳红色
    color: #fff;
    font-weight: 600;              // ✅ 加粗
    font-size: 24rpx;
    border: none;                    // ✅ CSS 边框
    box-shadow: 0 2rpx 8rpx rgba(229, 57, 53, 0.25);  // ✅ 轻微阴影

    /* ✅ 关键：去除已预约状态的边框 */
    &::after {
      border: none;                 // 去除 ::after 伪元素边框
    }

    &:active {
      background-color: #c62828;
      transform: scale(0.95);
      box-shadow: 0 1rpx 4rpx rgba(198, 40, 40, 0.35);
    }
  }
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
</style>