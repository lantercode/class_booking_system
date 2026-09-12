<template>
  <view class="schedule-container">
    <AppNavbar title="" :show-back="false" variant="default">
      <template #left>
        <view>排期列表</view>
      </template>
    </AppNavbar>

    <view class="main-content">
      <!-- 分类筛选栏 -->
      <scroll-view scroll-x class="filter-scroll" :show-scrollbar="false">
        <view class="filter-list">
          <view
            v-for="tab in filterTabs"
            :key="tab.value"
            class="filter-pill"
            :class="{ 'pill-active': selectedCategory === tab.value }"
            @tap="handleCategoryClick(tab.value)"
          >
            <text>{{ tab.label }}</text>
          </view>
        </view>
      </scroll-view>

      <!-- 日期选择栏 -->
      <scroll-view scroll-x class="date-scroll" :show-scrollbar="false">
        <view class="date-list">
          <view
            v-for="day in dateList"
            :key="day.date"
            class="date-pill"
            :class="{ 'pill-active': selectedDate === day.date }"
            @tap="selectDate(day.date)"
          >
            <text class="pill-day-name">{{ day.name }}</text>
            <text class="pill-day-date">{{ day.dateStr }}</text>
          </view>
        </view>
      </scroll-view>

      <scroll-view scroll-y class="schedule-scroll" :style="{ height: scrollViewHeight + 'px' }" :show-scrollbar="false">
        <view v-if="loading" class="loading-state">
          <text class="loading-text">加载中...</text>
        </view>
        <view v-else-if="displaySchedules.length === 0" class="empty-state">
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
              <view class="btn-wrapper">
                <button
                  class="book-btn"
                  :class="{
                    disabled: schedule._isDisabled,
                    booked: schedule._isBooked,
                    'no-card': schedule._statusClass === 'no_card',
                    'not-applicable': schedule._statusClass === 'not_applicable',
                    'insufficient': schedule._statusClass === 'insufficient',
                    'weekly-limit': schedule._statusClass === 'weekly_limit'
                  }"
                  :disabled="schedule._isDisabled"
                  @tap="schedule._isBooked ? handleBooking(schedule.id) : openCardSelector(schedule.id)"
                >
                  {{ schedule._btnText }}
                </button>
                <text v-if="schedule._cancelHint" class="cancel-hint">{{ schedule._cancelHint }}</text>
              </view>
            </view>
          </view>
        </view>
      </scroll-view>
    </view>

    <StudentTabBar currentRoute="/pages/student/schedule/index" />
    <AiAssistant :session-id="'student_' + (userId || 'default')" />
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { scheduleApi, bookingApi, courseTypeApi, membershipApi } from '@/api'
import { checkLogin } from '@/utils/auth'
import { formatTime, toAPIDateTime, isScheduleExpired, isWithinBookingWindow } from '@/utils/date'
import StudentTabBar from '@/components/StudentTabBar.vue'
import AiAssistant from '@/components/AiAssistant.vue'
import AppNavbar from '@/components/AppNavbar.vue'
import AppFilterTabs from '@/components/AppFilterTabs.vue'
import { extractList } from '@/utils/helpers'

const filterTabs = ref<Array<{ label: string; value: string }>>([
  { label: '全部', value: 'all' },
])
const selectedCategory = ref('all')
const selectedDate = ref('')
const daySchedules = ref<any[]>([])
const bookings = ref<any[]>([])
const loading = ref(false)
const userId = ref('')

// 会员卡相关
const membershipCards = ref<any[]>([])
const isLoadingCards = ref(false)

interface CardValidationResult {
  valid: boolean
  availableCards: any[]
  reason?: string
  reasonType?: 'no_card' | 'not_applicable' | 'insufficient' | 'weekly_limit' | 'expired'
}

const systemInfo = uni.getSystemInfoSync()
const navbarHeight = systemInfo.statusBarHeight + 44
const tabbarHeight = (100 / 750) * systemInfo.windowWidth
const filterAreaHeight = (280 / 750) * systemInfo.windowWidth
const scrollViewHeight = ref(Math.max(
  systemInfo.windowHeight - navbarHeight - tabbarHeight - filterAreaHeight,
  300
))

let isLoadingSchedules = false
let isLoadingBookings = false
let debounceTimer: number | null = null
let loadBookingsTimer: number | null = null
let retryTimer: number | null = null
let isUnmounted = false
let pendingDateRefresh: string | null = null

const dateList = computed(() => {
  const days: Array<{ date: string; name: string; dateStr: string }> = []
  const today = new Date()
  const dayNames = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

  for (let i = -2; i <= 14; i++) {
    const date = new Date(today)
    date.setDate(today.getDate() + i)
    const dateStr = date.toISOString().split('T')[0]
    days.push({
      date: dateStr,
      name: i === 0 ? '今日' : i === 1 ? '明日' : dayNames[date.getDay()],
      dateStr: `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`,
    })
  }
  return days
})

const displaySchedules = computed(() => {
  const bookedScheduleIds = new Set(bookings.value.map((b: any) => b.schedule_id))
  const now = Date.now()

  return daySchedules.value.map((schedule: any, index: number) => {
    const isBooked = bookedScheduleIds.has(schedule.id)
    const isFull = schedule.booked_count >= schedule.capacity
    const isExpired = isScheduleExpired(schedule.start_at)
    const isOutOfWindow = !isWithinBookingWindow(schedule.start_at, 14)
    
    // 计算是否在开课前90分钟内
    const startAtTime = new Date(schedule.start_at).getTime()
    const minutesBeforeStart = (startAtTime - now) / (1000 * 60)
    const isWithin90Min = minutesBeforeStart <= 90 && minutesBeforeStart > 0
    const isOngoing = minutesBeforeStart <= 0 && !isExpired
    
    const isDisabled = isExpired || isOutOfWindow || (isFull && !isBooked) || (isBooked && (isWithin90Min || isOngoing))

    let statusText: string
    let btnText: string
    let statusClass: string

    if (isBooked) {
      if (isOngoing) {
        statusText = '已预约'
        btnText = '不可取消'
        statusClass = 'booked'
      } else if (isWithin90Min) {
        statusText = '已预约'
        btnText = '不可取消'
        statusClass = 'booked'
      } else {
        statusText = '已预约'
        btnText = '取消'
        statusClass = 'booked'
      }
    } else if (isExpired) {
      statusText = '已完成'
      btnText = '已完成'
      statusClass = 'completed'
    } else if (isOutOfWindow) {
      statusText = '不可预约'
      btnText = '不可预约'
      statusClass = 'disabled'
    } else if (isFull) {
      statusText = '已满'
      btnText = '已满'
      statusClass = 'full'
    } else {
      // 检查会员卡状态
      const cardValidation = validateCardForSchedule(schedule)
      if (!cardValidation.valid) {
        switch (cardValidation.reasonType) {
          case 'no_card':
            statusText = '无会员卡'
            btnText = '无会员卡'
            statusClass = 'no_card'
            break
          case 'not_applicable':
            statusText = '不适用'
            btnText = '不适用'
            statusClass = 'not_applicable'
            break
          case 'insufficient':
            statusText = '余额不足'
            btnText = '余额不足'
            statusClass = 'insufficient'
            break
          case 'weekly_limit':
            statusText = '已达上限'
            btnText = '已达上限'
            statusClass = 'weekly_limit'
            break
          default:
            statusText = '可预约'
            btnText = '预约'
            statusClass = 'available'
        }
      } else {
        statusText = '可预约'
        btnText = '预约'
        statusClass = 'available'
      }
    }

    // 取消提示文案
    let cancelHint: string = ''
    if (isBooked && isOngoing) {
      cancelHint = '课程已开始，不可取消'
    } else if (isBooked && isWithin90Min) {
      cancelHint = '开课前90分钟内不可取消'
    }

    return {
      ...schedule,
      _key: schedule.id || `schedule-${selectedDate.value}-${index}`,
      _startTime: formatTime(schedule.start_at),
      _endTime: formatTime(schedule.end_at),
      _isBooked: isBooked,
      _isFull: isFull,
      _isDisabled: isDisabled || (!isBooked && !isExpired && !isOutOfWindow && !isFull && !validateCardForSchedule(schedule).valid),
      _statusClass: statusClass,
      _statusText: statusText,
      _btnText: btnText,
      _isWithin90Min: isWithin90Min,
      _isOngoing: isOngoing,
      _cancelHint: cancelHint,
      _cardValidation: !isBooked && !isExpired && !isOutOfWindow && !isFull ? validateCardForSchedule(schedule) : null,
    }
  })
})

// 会员卡验证函数
const validateCardForSchedule = (schedule: any): CardValidationResult => {
  if (membershipCards.value.length === 0) {
    return {
      valid: false,
      availableCards: [],
      reason: '您需要先办理会员卡才能预约课程',
      reasonType: 'no_card'
    }
  }

  // 筛选有效会员卡
  const now = new Date()
  const validCards = membershipCards.value.filter((card: any) => {
    if (card.status !== 1) return false // 1 = ACTIVE
    
    // 检查有效期
    if (card.expire_at && new Date(card.expire_at) < now) return false
    if (card.valid_from && new Date(card.valid_from) > now) return false
    
    // 检查次卡余额
    if (card.card_type === 'count') {
      const remaining = (card.total_credits || 0) - (card.used_credits || 0)
      if (remaining <= 0) return false
    }
    
    return true
  })

  if (validCards.length === 0) {
    // 检查是否有卡但都无效
    const hasExpiredCards = membershipCards.value.some((card: any) => {
      if (card.status === 1 && card.expire_at && new Date(card.expire_at) < now) return true
      if (card.status === 1 && card.card_type === 'count') {
        const remaining = (card.total_credits || 0) - (card.used_credits || 0)
        if (remaining <= 0) return true
      }
      return false
    })

    if (hasExpiredCards) {
      return {
        valid: false,
        availableCards: [],
        reason: '您的会员卡已过期或余额不足，请续费',
        reasonType: 'expired'
      }
    }

    return {
      valid: false,
      availableCards: [],
      reason: '您需要先办理会员卡才能预约课程',
      reasonType: 'no_card'
    }
  }

  // 检查适用课程类型
  const scheduleCourseTypeCode = schedule.course_type_code
  const typeApplicableCards = validCards.filter((card: any) => {
    if (!card.applicable_course_type_codes || card.applicable_course_type_codes.length === 0) {
      return true // 适用于所有课程类型
    }
    if (!scheduleCourseTypeCode) return true
    return card.applicable_course_type_codes.includes(scheduleCourseTypeCode)
  })

  if (typeApplicableCards.length === 0) {
    return {
      valid: false,
      availableCards: [],
      reason: '当前会员卡不适用于此课程类型',
      reasonType: 'not_applicable'
    }
  }

  // 检查适用课程
  const applicableCards = typeApplicableCards.filter((card: any) => {
    if (!card.applicable_course_ids || card.applicable_course_ids.length === 0) {
      return true // 适用于所有课程
    }
    return card.applicable_course_ids.includes(schedule.course_id)
  })

  if (applicableCards.length === 0) {
    return {
      valid: false,
      availableCards: [],
      reason: '当前会员卡不适用于此课程',
      reasonType: 'not_applicable'
    }
  }

  // 检查每周使用次数限制
  const cardsWithinWeeklyLimit = applicableCards.filter((card: any) => {
    if (!card.max_weekly_usage) return true // 无限制
    
    // TODO: 需要后端API支持查询本周使用次数
    // 暂时假设未超限
    return true
  })

  if (cardsWithinWeeklyLimit.length === 0) {
    return {
      valid: false,
      availableCards: [],
      reason: '本周使用次数已达上限',
      reasonType: 'weekly_limit'
    }
  }

  return {
    valid: true,
    availableCards: cardsWithinWeeklyLimit
  }
}

// 加载会员卡
const loadMembershipCards = async () => {
  if (isLoadingCards.value) return
  isLoadingCards.value = true

  try {
    const result = await membershipApi.getMyCards()
    if (isUnmounted) return

    const responseData = result?.data as any
    let cards: any[] = []

    if (responseData?.items && Array.isArray(responseData.items)) {
      cards = responseData.items
    } else if (Array.isArray(responseData)) {
      cards = responseData
    }

    membershipCards.value = cards
  } catch (error) {
    console.error('加载会员卡失败:', error)
  } finally {
    isLoadingCards.value = false
  }
}

// 打开预约确认页
const openCardSelector = (scheduleId: number) => {
  const schedule = daySchedules.value.find((s: any) => s.id === scheduleId)
  if (!schedule) return

  const validation = validateCardForSchedule(schedule)
  if (!validation.valid) {
    uni.showToast({
      title: validation.reason || '无法预约',
      icon: 'none',
      duration: 2000
    })
    return
  }

  // 跳转到预约确认页
  uni.navigateTo({
    url: `/pages/student/booking-confirm/index?scheduleId=${scheduleId}`
  })
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
  loadCourseTypes()
  loadSchedules()
  loadBookings()
  loadMembershipCards()

  uni.$on('bookingSuccess', handleBookingSuccess)
})

const loadCourseTypes = async () => {
  try {
    const result = await courseTypeApi.list({ status: 1 })
    if (isUnmounted) return
    
    const responseData = result?.data as any
    let items: any[] = []
    
    if (responseData?.items && Array.isArray(responseData.items)) {
      items = responseData.items
    } else if (Array.isArray(responseData)) {
      items = responseData
    }
    
    // 构建 filter tabs，使用课程类型名称作为显示标签
    const tabs: Array<{ label: string; value: string }> = [
      { label: '全部', value: 'all' },
    ]
    
    items.forEach((type: any) => {
      if (type.code && type.status === 1) {
        tabs.push({ label: type.name, value: type.code })
      }
    })
    
    filterTabs.value = tabs
  } catch (error) {
    console.error('加载课程类型失败:', error)
  }
}

onUnmounted(() => {
  isUnmounted = true
  if (debounceTimer) { clearTimeout(debounceTimer); debounceTimer = null }
  if (loadBookingsTimer) { clearTimeout(loadBookingsTimer); loadBookingsTimer = null }
  if (retryTimer) { clearTimeout(retryTimer); retryTimer = null }
  uni.$off('bookingSuccess', handleBookingSuccess)
})

const loadSchedules = async () => {
  if (isLoadingSchedules) {
    pendingDateRefresh = selectedDate.value
    return
  }

  isLoadingSchedules = true
  loading.value = true

  try {
    const apiDateTime = toAPIDateTime(selectedDate.value)
    const params: any = {
      start_from: apiDateTime.start,
      start_to: apiDateTime.end,
      status: 1,
    }
    if (selectedCategory.value !== 'all') {
      params.course_type_code = selectedCategory.value
    }

    const result = await scheduleApi.list(params)
    if (isUnmounted) return

    const responseData = result?.data as any
    let finalList: any[] = []

    if (responseData?.items && Array.isArray(responseData.items)) {
      finalList = responseData.items
    } else if (Array.isArray(responseData)) {
      finalList = responseData
    } else {
      finalList = extractList(result)
    }

    daySchedules.value = finalList
    loading.value = false
    await nextTick()

    loadBookingsTimer = setTimeout(() => {
      loadBookings()
      loadBookingsTimer = null
    }, 150) as unknown as number
  } catch (error) {
    console.error('加载排期失败:', error)
    uni.showToast({ title: '加载失败', icon: 'none' })
    isLoadingSchedules = false
    loading.value = false
  }
}

const onAllDataLoaded = () => {
  isLoadingSchedules = false
  if (pendingDateRefresh && pendingDateRefresh !== selectedDate.value) {
    const refreshDate = pendingDateRefresh
    pendingDateRefresh = null
    retryTimer = setTimeout(() => { loadSchedules(); retryTimer = null }, 50) as unknown as number
  }
}

const loadBookings = async () => {
  if (isLoadingBookings) return
  isLoadingBookings = true

  try {
    const result = await bookingApi.list({ status: 1 })
    if (isUnmounted) return

    const responseData = result?.data as any
    let finalList: any[] = []

    if (responseData?.items && Array.isArray(responseData.items)) {
      finalList = responseData.items
    } else if (Array.isArray(responseData)) {
      finalList = responseData
    } else {
      finalList = extractList(result)
    }

    bookings.value = finalList
  } catch (error) {
    console.error('加载预约失败:', error)
  } finally {
    isLoadingBookings = false
    onAllDataLoaded()
  }
}

const handleCategoryClick = (value: string) => {
  if (value === selectedCategory.value) return
  selectedCategory.value = value
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => { loadSchedules(); debounceTimer = null }, 100) as unknown as number
}

const selectDate = (date: string) => {
  if (date === selectedDate.value) return
  selectedDate.value = date

  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => { loadSchedules(); debounceTimer = null }, 100) as unknown as number
}

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

  // 已预约的课程，检查是否在90分钟限制内或课程进行中
  if (isScheduleBooked(scheduleId)) {
    if (schedule._isWithin90Min) {
      uni.showModal({
        title: '无法取消',
        content: '开课前90分钟内不可取消预约，请准时参加课程',
        showCancel: false,
        confirmText: '知道了',
      })
      return
    }
    
    if (schedule._isOngoing) {
      uni.showModal({
        title: '无法取消',
        content: '课程已开始，不可取消预约',
        showCancel: false,
        confirmText: '知道了',
      })
      return
    }

    uni.showModal({
      title: '取消预约',
      content: '确定要取消此预约吗？',
      success: async (res) => {
        if (res.confirm) await cancelBooking(scheduleId)
      },
    })
    return
  }

  // 跳转到预约确认页
  uni.navigateTo({
    url: `/pages/student/booking-confirm/index?scheduleId=${scheduleId}`
  })
}

const cancelBooking = async (scheduleId: number) => {
  try {
    const booking = bookings.value.find((b: any) => b.schedule_id === scheduleId)
    if (!booking) {
      uni.showToast({ title: '未找到预约记录', icon: 'none' })
      return
    }

    if (booking.start_at) {
      const startTime = new Date(booking.start_at).getTime()
      const now = Date.now()
      const minutesBefore = (startTime - now) / (1000 * 60)
      if (minutesBefore <= 90) {
        uni.showToast({ title: '开课前90分钟内不可取消', icon: 'none' })
        return
      }
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

const handleBookingSuccess = async () => {
  console.log('🎉 收到预约成功事件，刷新排期和预约数据')
  await Promise.all([loadSchedules(), loadBookings(), loadMembershipCards()])
}
</script>

<style lang="scss">
.schedule-container {
  @include page-container;
  overflow: visible;
}

.main-content {
  @include main-content;
  overflow: visible;
  padding: $space-md $space-md $space-sm;
}

// 分类筛选栏
.filter-scroll {
  white-space: nowrap;
  margin-bottom: $space-md;
  padding: 0;
  overflow: visible;
  @include hide-scrollbar;
}

.filter-list {
  display: inline-flex;
  gap: $space-xs;
  padding: 6rpx 0;
  align-items: center;
}

// 日期选择栏
.date-scroll {
  white-space: nowrap;
  margin-bottom: $space-md;
  padding: 0;
  @include hide-scrollbar;
}

.date-list {
  display: inline-flex;
  gap: $space-xs;
  padding: 0;
  align-items: center;
}

// 分类 Pill
.filter-pill {
  @include badge-base(20rpx 32rpx, $radius-full, $font-size-body_sm);
  background: rgba(255, 255, 255, 0.85);
  border: 2rpx solid rgba(255, 255, 255, 0.28);
  color: $text-secondary;
  box-shadow: 0 2rpx 6rpx rgba(0, 0, 0, 0.08);
  box-sizing: border-box;
  line-height: 1.2;
  transition: background $duration-fast $ease-standard,
              color $duration-fast $ease-standard,
              border-color $duration-fast $ease-standard,
              box-shadow $duration-fast $ease-standard,
              transform $duration-fast $ease-standard;

  &:active {
    transform: scale(0.96);
  }

  &.pill-active {
    background: $primary-gradient;
    color: $text-primary;
    border-color: transparent;
    box-shadow: 0 4rpx 16rpx rgba(102, 126, 234, 0.3);
  }
}

// 日期 Pill
.date-pill {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 64rpx;
  padding: $space-xs $space-sm;
  border-radius: $radius-md;
  transition: all $duration-fast $ease-standard;
  background: rgba(255, 255, 255, 0.85);
  border: 2rpx solid rgba(255, 255, 255, 0.28);
  box-shadow: 0 2rpx 6rpx rgba(0, 0, 0, 0.08);

  &:active {
    transform: scale(0.96);
  }

  &.pill-active {
    background: $primary-solid;

    .pill-day-name, .pill-day-date {
      color: #fff;
    }
  }
}

.pill-day-name {
  font-size: $font-size-caption;
  color: $text-tertiary;
  margin-bottom: 2rpx;
}

.pill-day-date {
  font-size: $font-size-body_sm;
  color: $text-primary;
  font-weight: $font-weight-medium;
}

.schedule-scroll {
  padding: 0;
  padding-bottom: 120rpx;
  box-sizing: border-box;

  // 完全隐藏滚动条（包括轨道）
  &::-webkit-scrollbar {
    display: none;
    width: 0;
    height: 0;
  }
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
  color: $primary-solid;
}

.time-line {
  width: 2rpx;
  height: 40rpx;
  background: $border-light;
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
    background: $primary-bg;
    color: $primary-solid;
  }

  &.full {
    background: $error-bg;
    color: $error-color;
  }

  &.available {
    background: $success-bg;
    color: $success-color;
  }

  &.ongoing {
    background: $warning-bg;
    color: $warning-color;
  }

  &.completed {
    background: $bg-tertiary;
    color: $text-tertiary;
  }

  &.disabled {
    background: $bg-tertiary;
    color: $text-tertiary;
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
  font-size: $font-size-body_sm;
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

.btn-wrapper {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: $space-2xs;
}

.cancel-hint {
  font-size: $font-size-caption;
  color: $text-tertiary;
  line-height: 1.2;
}

.count {
  font-size: $font-size-body_sm;
  color: $text-tertiary;
  order: -1;
  margin-right: auto;
}

.book-btn {
  padding: $space-xs $space-lg;
  background: $primary-gradient;
  color: #fff;
  border-radius: $radius-2xl;
  border: none;
  font-size: $font-size-body_sm;
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
      background: $accent-solid;
      color: #fff;
      opacity: 0.75;

      &::after {
        border: none;
      }
    }

    &.ongoing {
      background: $warning-bg;
      color: $warning-color;
      opacity: 0.8;

      &::after {
        border: none;
      }
    }
  }

  &.booked {
    background-color: #e53935;
    color: #fff;
    font-weight: 600;
    font-size: 24rpx;
    border: none;
    box-shadow: 0 2rpx 8rpx rgba(229, 57, 53, 0.25);

    &::after {
      border: none;
    }

    &:active {
      background-color: #c62828;
      transform: scale(0.95);
      box-shadow: 0 1rpx 4rpx rgba(198, 40, 40, 0.35);
    }
  }

  // 无会员卡状态
  &.no-card {
    background: $bg-tertiary;
    color: $text-disabled;
    box-shadow: none;
    border: 1rpx solid $border-light;

    &::after {
      border: none;
    }
  }

  // 不适用状态
  &.not-applicable {
    background: $warning-bg;
    color: $warning-color;
    box-shadow: none;
    border: 1rpx solid $warning-border;

    &::after {
      border: none;
    }
  }

  // 余额不足状态
  &.insufficient {
    background: $warning-bg;
    color: $warning-color;
    box-shadow: none;
    border: 1rpx solid $warning-border;

    &::after {
      border: none;
    }
  }

  // 每周上限状态
  &.weekly-limit {
    background: $warning-bg;
    color: $warning-color;
    box-shadow: none;
    border: 1rpx solid $warning-border;

    &::after {
      border: none;
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