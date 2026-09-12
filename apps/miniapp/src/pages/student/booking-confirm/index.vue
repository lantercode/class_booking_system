<template>
  <view class="booking-confirm-page">
    <AppNavbar title="预约确认" :show-back="true" variant="default" />

    <scroll-view scroll-y class="confirm-scroll" :style="{ height: scrollViewHeight + 'px' }" :show-scrollbar="false">
      <!-- 加载状态 -->
      <view v-if="loading" class="loading-state">
        <text class="loading-text">加载中...</text>
      </view>

      <view v-else class="confirm-content">
        <!-- 课程信息卡片 -->
        <view class="info-card">
          <view class="card-header">
            <text class="card-label">课程信息</text>
          </view>
          <view class="card-body">
            <text class="course-name">{{ schedule.course_name || '未知课程' }}</text>
            <view class="info-row">
              <text class="info-icon">📅</text>
              <text class="info-text">{{ formatDate(schedule.start_at) }}</text>
            </view>
            <view class="info-row">
              <text class="info-icon">⏰</text>
              <text class="info-text">{{ formatTime(schedule.start_at) }} - {{ formatTime(schedule.end_at) }}</text>
            </view>
            <view class="info-row">
              <text class="info-icon">📍</text>
              <text class="info-text">{{ schedule.classroom_name || '未安排教室' }}</text>
            </view>
            <view class="info-row">
              <text class="info-icon">👨‍🏫</text>
              <text class="info-text">{{ schedule.teacher_name || '未知' }}</text>
            </view>
            <view class="info-row">
              <text class="info-icon">👥</text>
              <text class="info-text">剩余 {{ schedule.capacity - schedule.booked_count }}/{{ schedule.capacity }} 人</text>
            </view>
          </view>
        </view>

        <!-- 会员卡信息卡片 -->
        <view class="card-card">
          <view class="card-header">
            <text class="card-label">使用会员卡</text>
            <view v-if="availableCards.length > 1" class="switch-btn" @tap="showCardSelector = true">
              <text class="switch-text">切换</text>
              <text class="switch-icon">›</text>
            </view>
          </view>
          <view class="card-body">
            <view class="selected-card-info">
              <view class="card-icon-wrapper" :class="'card-type-' + selectedCard?.card_type">
                <text class="card-icon">{{ getCardIcon(selectedCard?.card_type) }}</text>
              </view>
              <view class="card-details">
                <text class="card-name">{{ selectedCard?.product_name || getCardTypeText(selectedCard?.card_type) }}</text>
                <text class="card-remaining">{{ getCardRemainingText(selectedCard) }}</text>
                <text class="card-applicable">{{ getCardApplicableText(selectedCard) }}</text>
              </view>
              <view class="card-type-badge" :class="'type-' + selectedCard?.card_type">
                <text>{{ getCardTypeText(selectedCard?.card_type) }}</text>
              </view>
            </view>
          </view>
        </view>

        <!-- 注意事项 -->
        <view class="notice-card">
          <view class="notice-header">
            <text class="notice-title">注意事项</text>
          </view>
          <view class="notice-list">
            <view class="notice-item">
              <text class="notice-dot">•</text>
              <text class="notice-text">开课前90分钟内不可取消预约</text>
            </view>
            <view class="notice-item">
              <text class="notice-dot">•</text>
              <text class="notice-text">请准时到达教室，迟到可能影响上课</text>
            </view>
            <view class="notice-item">
              <text class="notice-dot">•</text>
              <text class="notice-text">如需取消请提前在"我的预约"中操作</text>
            </view>
          </view>
        </view>
      </view>
    </scroll-view>

    <!-- 底部操作栏 -->
    <view class="action-bar" :style="{ paddingBottom: safeAreaBottom + 'px' }">
      <button class="action-btn cancel-btn" @tap="handleCancel">取消</button>
      <button class="action-btn confirm-btn" :disabled="!selectedCardId" @tap="handleConfirm">确认预约</button>
    </view>

    <!-- 会员卡选择弹窗 -->
    <view v-if="showCardSelector" class="card-selector-mask" @tap="showCardSelector = false">
      <view class="card-selector-popup" @tap.stop>
        <view class="selector-header">
          <text class="selector-title">选择会员卡</text>
          <view class="selector-close" @tap="showCardSelector = false">
            <text class="close-icon">×</text>
          </view>
        </view>

        <scroll-view scroll-y class="card-list-scroll">
          <view
            v-for="card in allCardsWithStatus"
            :key="card.id"
            class="card-option"
            :class="{ 
              'card-selected': selectedCardId === card.id && card.isAvailable,
              'card-disabled': !card.isAvailable
            }"
            @tap="handleCardSelect(card)"
          >
            <view class="card-option-left">
              <view 
                class="card-radio" 
                :class="{ 
                  'radio-checked': selectedCardId === card.id && card.isAvailable,
                  'radio-disabled': !card.isAvailable
                }"
              >
                <view v-if="selectedCardId === card.id && card.isAvailable" class="radio-dot"></view>
              </view>
              <view class="card-option-info">
                <text class="card-option-name">{{ card.product_name || getCardTypeText(card.card_type) }}</text>
                <text class="card-option-remaining">{{ getCardRemainingText(card) }}</text>
                <text class="card-option-applicable">{{ getCardApplicableText(card) }}</text>
                <text v-if="!card.isAvailable && card.unavailableReason" class="card-option-reason">{{ card.unavailableReason }}</text>
              </view>
            </view>
            <view class="card-option-type">
              <text class="type-badge" :class="'type-' + card.card_type">{{ getCardTypeText(card.card_type) }}</text>
            </view>
          </view>
        </scroll-view>

        <view class="selector-footer">
          <button class="footer-btn confirm-btn-small" :disabled="!selectedCardId" @tap="showCardSelector = false">确定</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { scheduleApi, bookingApi, membershipApi, courseTypeApi } from '@/api'
import { checkLogin } from '@/utils/auth'
import { formatTime } from '@/utils/date'
import AppNavbar from '@/components/AppNavbar.vue'

const scheduleId = ref<number>(0)
const schedule = ref<any>({})
const membershipCards = ref<any[]>([])
const selectedCardId = ref<number | null>(null)
const showCardSelector = ref(false)
const loading = ref(true)
const courseTypeMap = ref<Record<string, string>>({})

const systemInfo = uni.getSystemInfoSync()
const navbarHeight = systemInfo.statusBarHeight + 44
const actionBarHeight = 120
const scrollViewHeight = ref(Math.max(
  systemInfo.windowHeight - navbarHeight - actionBarHeight,
  300
))
const safeAreaBottom = systemInfo.safeAreaInsets?.bottom || 0

// 所有会员卡（包含可用和不可用）
const allCardsWithStatus = computed(() => {
  if (!schedule.value.course_id) return []
  
  const now = new Date()
  const scheduleCourseTypeCode = schedule.value.course_type_code

  return membershipCards.value.map((card: any) => {
    let isAvailable = true
    let unavailableReason = ''

    if (card.status !== 1) {
      isAvailable = false
      unavailableReason = '会员卡已停用'
    } else if (card.expire_at && new Date(card.expire_at) < now) {
      isAvailable = false
      unavailableReason = '会员卡已过期'
    } else if (card.valid_from && new Date(card.valid_from) > now) {
      isAvailable = false
      unavailableReason = '会员卡未生效'
    } else if (card.card_type === 'count') {
      const remaining = (card.total_credits || 0) - (card.used_credits || 0)
      if (remaining <= 0) {
        isAvailable = false
        unavailableReason = '余额不足'
      }
    }

    if (isAvailable && card.applicable_course_type_codes && card.applicable_course_type_codes.length > 0) {
      if (scheduleCourseTypeCode && !card.applicable_course_type_codes.includes(scheduleCourseTypeCode)) {
        isAvailable = false
        unavailableReason = '不适用于此课程类型'
      }
    }

    if (isAvailable && card.applicable_course_ids && card.applicable_course_ids.length > 0) {
      if (!card.applicable_course_ids.includes(schedule.value.course_id)) {
        isAvailable = false
        unavailableReason = '不适用于此课程'
      }
    }

    return {
      ...card,
      isAvailable,
      unavailableReason
    }
  })
})

// 可用会员卡列表
const availableCards = computed(() => {
  return allCardsWithStatus.value.filter(card => card.isAvailable)
})

// 选中的会员卡
const selectedCard = computed(() => {
  return availableCards.value.find((c: any) => c.id === selectedCardId.value) || null
})

// 格式化日期
const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const weekDays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  const weekDay = weekDays[date.getDay()]
  return `${month}-${day} ${weekDay}`
}

// 获取会员卡类型文本
const getCardTypeText = (cardType: string) => {
  const typeMap: Record<string, string> = {
    count: '次卡',
    period: '期卡',
    unlimited: '无限卡'
  }
  return typeMap[cardType] || cardType
}

// 获取会员卡图标
const getCardIcon = (cardType: string) => {
  const iconMap: Record<string, string> = {
    count: '🎫',
    period: '📅',
    unlimited: '️'
  }
  return iconMap[cardType] || ''
}

// 获取会员卡剩余信息
const getCardRemainingText = (card: any) => {
  if (!card) return ''
  if (card.card_type === 'count') {
    const remaining = (card.total_credits || 0) - (card.used_credits || 0)
    return `剩余 ${remaining} 次`
  }
  if (card.card_type === 'period') {
    if (card.expire_at) {
      const expireDate = new Date(card.expire_at)
      const now = new Date()
      const days = Math.floor((expireDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
      return `剩余 ${Math.max(0, days)} 天`
    }
    return '有效期内'
  }
  if (card.card_type === 'unlimited') {
    return '永久有效'
  }
  return ''
}

// 获取适用课程文本
const getCardApplicableText = (card: any) => {
  if (!card) return ''
  
  // 优先检查课程类型限制
  if (card.applicable_course_type_codes && card.applicable_course_type_codes.length > 0) {
    const typeNames = card.applicable_course_type_codes
      .map((code: string) => courseTypeMap.value[code] || code)
      .join('、')
    return `适用：${typeNames}`
  }
  
  // 其次检查具体课程限制
  if (card.applicable_course_ids && card.applicable_course_ids.length > 0) {
    return `适用 ${card.applicable_course_ids.length} 门课程`
  }
  
  return '适用全部课程'
}

// 获取扣除后的剩余次数
const getRemainingAfterDeduction = () => {
  if (!selectedCard.value) return 0
  if (selectedCard.value.card_type === 'count') {
    const remaining = (selectedCard.value.total_credits || 0) - (selectedCard.value.used_credits || 0)
    return remaining - 1
  }
  return '不限'
}

// 选择会员卡
const handleCardSelect = (card: any) => {
  if (!card.isAvailable) {
    uni.showToast({
      title: card.unavailableReason || '该卡不可用',
      icon: 'none',
      duration: 2000
    })
    return
  }
  selectedCardId.value = card.id
}

// 智能匹配默认选中的会员卡
const getDefaultSelectedCard = (cards: any[]) => {
  if (!cards || cards.length === 0) return null
  if (cards.length === 1) return cards[0].id

  const scheduleCourseTypeCode = schedule.value.course_type_code

  const specificCards = cards.filter((card: any) => {
    if (!card.applicable_course_ids || card.applicable_course_ids.length === 0) return false
    return card.applicable_course_ids.includes(schedule.value.course_id)
  })

  if (specificCards.length === 1) return specificCards[0].id

  if (specificCards.length > 1) {
    const countCards = specificCards.filter((c: any) => c.card_type === 'count')
    if (countCards.length > 0) {
      countCards.sort((a: any, b: any) => {
        const aRemain = (a.total_credits || 0) - (a.used_credits || 0)
        const bRemain = (b.total_credits || 0) - (b.used_credits || 0)
        return bRemain - aRemain
      })
      return countCards[0].id
    }
    return specificCards[0].id
  }

  const typeMatchedCards = cards.filter((card: any) => {
    if (!card.applicable_course_type_codes || card.applicable_course_type_codes.length === 0) return true
    if (!scheduleCourseTypeCode) return true
    return card.applicable_course_type_codes.includes(scheduleCourseTypeCode)
  })

  if (typeMatchedCards.length > 0) {
    const priorityOrder: Record<string, number> = {
      unlimited: 1,
      period: 2,
      count: 3
    }
    typeMatchedCards.sort((a: any, b: any) => {
      const aPriority = priorityOrder[a.card_type] || 99
      const bPriority = priorityOrder[b.card_type] || 99
      return aPriority - bPriority
    })
    return typeMatchedCards[0].id
  }

  const priorityOrder: Record<string, number> = {
    unlimited: 1,
    period: 2,
    count: 3
  }
  cards.sort((a: any, b: any) => {
    const aPriority = priorityOrder[a.card_type] || 99
    const bPriority = priorityOrder[b.card_type] || 99
    return aPriority - bPriority
  })
  return cards[0].id
}

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    // 加载排期详情
    const scheduleRes = await scheduleApi.get(scheduleId.value)
    const scheduleData = scheduleRes?.data as any
    if (scheduleData) {
      schedule.value = scheduleData
    }

    // 加载课程类型映射
    try {
      const typesRes = await courseTypeApi.list()
      const typesData = typesRes?.data as any
      if (typesData?.items && Array.isArray(typesData.items)) {
        typesData.items.forEach((type: any) => {
          courseTypeMap.value[type.code] = type.name
        })
      }
    } catch (e) {
      console.warn('加载课程类型失败:', e)
    }

    // 加载会员卡
    const cardsRes = await membershipApi.getMyCards()
    const cardsData = cardsRes?.data as any
    let cards: any[] = []
    if (cardsData?.items && Array.isArray(cardsData.items)) {
      cards = cardsData.items
    } else if (Array.isArray(cardsData)) {
      cards = cardsData
    }
    membershipCards.value = cards

    // 智能匹配默认卡
    if (availableCards.value.length > 0) {
      selectedCardId.value = getDefaultSelectedCard(availableCards.value)
    }
  } catch (error) {
    console.error('加载数据失败:', error)
    uni.showToast({ title: '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

// 取消
const handleCancel = () => {
  uni.navigateBack()
}

// 确认预约
const handleConfirm = async () => {
  if (!selectedCardId.value) {
    uni.showToast({ title: '请选择会员卡', icon: 'none' })
    return
  }

  uni.showModal({
    title: '确认预约',
    content: '确定要预约此课程吗？',
    success: async (res) => {
      if (res.confirm) {
        try {
          const result = await bookingApi.create({
            schedule_id: scheduleId.value,
            membership_card_id: selectedCardId.value
          })
          if (result.code === 0 || result.code === 200) {
            uni.showToast({ title: '预约成功', icon: 'success' })
            setTimeout(() => {
              uni.$emit('bookingSuccess')
              uni.navigateBack()
            }, 1500)
          } else {
            uni.showToast({ title: result.msg || '预约失败', icon: 'none' })
          }
        } catch (error: any) {
          const errorMsg = error?.response?.data?.msg || error?.msg || '预约失败'
          uni.showToast({ title: errorMsg, icon: 'none' })
        }
      }
    }
  })
}

onMounted(() => {
  if (!checkLogin('student')) return

  const pages = getCurrentPages()
  const currentPage = pages[pages.length - 1] as any
  const options = currentPage.options || {}
  scheduleId.value = parseInt(options.scheduleId) || 0

  if (!scheduleId.value) {
    uni.showToast({ title: '参数错误', icon: 'none' })
    setTimeout(() => uni.navigateBack(), 1500)
    return
  }

  loadData()
})
</script>

<style lang="scss" scoped>
@import '@/styles/theme/_variables.scss';
@import '@/styles/theme/_mixins.scss';

.booking-confirm-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: $bg-primary;
}

.confirm-scroll {
  flex: 1;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 120rpx 0;
}

.loading-text {
  font-size: $font-size-body;
  color: $text-tertiary;
}

.confirm-content {
  padding: $space-md;
  padding-bottom: calc($space-xl + 120rpx);
}

// 信息卡片
.info-card, .card-card, .deduction-card, .notice-card {
  background: $bg-elevated;
  border-radius: $radius-lg;
  margin-bottom: $space-md;
  box-shadow: $shadow-card;
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: $space-sm $space-md;
  border-bottom: 1rpx solid $divider-color;
}

.card-label {
  font-size: $font-size-body;
  font-weight: $font-weight-semibold;
  color: $text-primary;
}

.card-body {
  padding: $space-md;
}

// 课程信息
.course-name {
  font-size: $font-size-h4;
  font-weight: $font-weight-semibold;
  color: $text-primary;
  display: block;
  margin-bottom: $space-sm;
}

.info-row {
  display: flex;
  align-items: center;
  gap: $space-xs;
  margin-bottom: $space-xs;

  &:last-child {
    margin-bottom: 0;
  }
}

.info-icon {
  font-size: $font-size-body;
  width: 32rpx;
  text-align: center;
}

.info-text {
  font-size: $font-size-body_sm;
  color: $text-secondary;
}

// 切换按钮
.switch-btn {
  display: flex;
  align-items: center;
  gap: 4rpx;
  padding: 8rpx 16rpx;
  border-radius: $radius-full;
  background: $primary-bg;

  &:active {
    opacity: 0.8;
  }
}

.switch-text {
  font-size: $font-size-caption;
  color: $primary-solid;
  font-weight: $font-weight-medium;
}

.switch-icon {
  font-size: $font-size-caption;
  color: $primary-solid;
}

// 选中卡片信息
.selected-card-info {
  display: flex;
  align-items: center;
  gap: $space-sm;
}

.card-icon-wrapper {
  width: 80rpx;
  height: 80rpx;
  border-radius: $radius-md;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  &.card-type-count {
    background: linear-gradient(135deg, rgba(255, 236, 210, 0.4), rgba(252, 182, 159, 0.4));
  }

  &.card-type-period {
    background: linear-gradient(135deg, rgba(168, 237, 234, 0.4), rgba(254, 214, 227, 0.4));
  }

  &.card-type-unlimited {
    background: linear-gradient(135deg, rgba(210, 153, 194, 0.4), rgba(254, 249, 215, 0.4));
  }
}

.card-icon {
  font-size: 40rpx;
}

.card-details {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.card-name {
  font-size: $font-size-body;
  font-weight: $font-weight-medium;
  color: $text-primary;
}

.card-remaining {
  font-size: $font-size-caption;
  color: $text-secondary;
}

.card-applicable {
  font-size: $font-size-tiny;
  color: $text-tertiary;
}

.card-type-badge {
  padding: 6rpx 20rpx;
  border-radius: $radius-full;
  font-size: $font-size-tiny;
  font-weight: $font-weight-medium;
  flex-shrink: 0;

  &.type-count {
    background: linear-gradient(135deg, rgba(255, 236, 210, 0.6), rgba(252, 182, 159, 0.6));
    color: #c97a5e;
  }

  &.type-period {
    background: linear-gradient(135deg, rgba(168, 237, 234, 0.6), rgba(254, 214, 227, 0.6));
    color: #6ba3a0;
  }

  &.type-unlimited {
    background: linear-gradient(135deg, rgba(210, 153, 194, 0.6), rgba(254, 249, 215, 0.6));
    color: #9b6b8a;
  }
}

// 扣次提示
.deduction-card {
  display: flex;
  align-items: flex-start;
  gap: $space-sm;
  padding: $space-md;
  background: $warning-bg;
  border: 1rpx solid $warning-border;
}

.deduction-icon {
  font-size: 36rpx;
  flex-shrink: 0;
  margin-top: 2rpx;
}

.deduction-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.deduction-text {
  font-size: $font-size-body_sm;
  color: $warning-color;
}

.deduction-highlight {
  font-weight: $font-weight-semibold;
  font-size: $font-size-body;
}

.deduction-remaining {
  font-size: $font-size-caption;
  color: $text-secondary;
}

// 注意事项
.notice-header {
  padding: $space-sm $space-md;
  border-bottom: 1rpx solid $divider-color;
}

.notice-title {
  font-size: $font-size-body;
  font-weight: $font-weight-semibold;
  color: $text-primary;
}

.notice-list {
  padding: $space-md;
}

.notice-item {
  display: flex;
  align-items: flex-start;
  gap: $space-xs;
  margin-bottom: $space-xs;

  &:last-child {
    margin-bottom: 0;
  }
}

.notice-dot {
  font-size: $font-size-body;
  color: $text-tertiary;
  line-height: 1.5;
}

.notice-text {
  font-size: $font-size-caption;
  color: $text-secondary;
  line-height: 1.5;
}

// 底部操作栏
.action-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  gap: $space-sm;
  padding: $space-sm $space-md;
  background: $bg-elevated;
  border-top: 1rpx solid $divider-color;
  box-shadow: 0 -4rpx 16rpx rgba(0, 0, 0, 0.05);
}

.action-btn {
  flex: 1;
  height: 88rpx;
  border-radius: $radius-2xl;
  border: none;
  font-size: $font-size-body;
  font-weight: $font-weight-medium;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all $duration-fast $ease-standard;

  &::after {
    border: none;
  }

  &:active {
    transform: scale(0.96);
  }
}

.cancel-btn {
  background: $bg-tertiary;
  color: $text-secondary;
}

.confirm-btn {
  background: $primary-gradient;
  color: #fff;
  box-shadow: $shadow-button;

  &[disabled] {
    background: $bg-tertiary;
    color: $text-disabled;
    box-shadow: none;
  }
}

// 会员卡选择弹窗
.card-selector-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: $bg-overlay;
  z-index: 1000;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  animation: fadeIn 0.2s ease;
}

.card-selector-popup {
  width: 100%;
  max-height: 70vh;
  background: $bg-elevated;
  border-radius: $radius-3xl $radius-3xl 0 0;
  padding: $space-lg $space-md;
  padding-bottom: calc($space-lg + env(safe-area-inset-bottom));
  animation: slideUp 0.3s cubic-bezier(0.22, 0.61, 0.36, 1);
  display: flex;
  flex-direction: column;
}

.selector-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: $space-md;
}

.selector-title {
  font-size: $font-size-h4;
  font-weight: $font-weight-semibold;
  color: $text-primary;
}

.selector-close {
  width: 56rpx;
  height: 56rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: $radius-full;
  background: $bg-tertiary;

  &:active {
    background: $bg-secondary;
  }
}

.close-icon {
  font-size: 40rpx;
  color: $text-secondary;
  line-height: 1;
}

.card-list-scroll {
  flex: 1;
  max-height: 500rpx;
  margin-bottom: $space-md;
}

.card-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: $space-sm $space-md;
  margin-bottom: $space-xs;
  border-radius: $radius-md;
  border: 2rpx solid $border-subtle;
  background: $bg-elevated;
  transition: all $duration-fast $ease-standard;

  &:active {
    transform: scale(0.98);
  }

  &.card-selected {
    border-color: $primary-solid;
    background: $primary-bg;
  }

  &.card-disabled {
    opacity: 0.5;
    background: $bg-tertiary;
    border-color: $border-light;

    &:active {
      transform: none;
    }
  }
}

.card-option-left {
  display: flex;
  align-items: center;
  gap: $space-sm;
  flex: 1;
}

.card-radio {
  width: 36rpx;
  height: 36rpx;
  border-radius: $radius-full;
  border: 2rpx solid $border-normal;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all $duration-fast $ease-standard;

  &.radio-checked {
    border-color: $primary-solid;
    background: $primary-solid;
  }

  &.radio-disabled {
    border-color: $border-light;
    background: $bg-tertiary;
  }
}

.radio-dot {
  width: 16rpx;
  height: 16rpx;
  border-radius: $radius-full;
  background: #fff;
}

.card-option-info {
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.card-option-name {
  font-size: $font-size-body;
  font-weight: $font-weight-medium;
  color: $text-primary;
}

.card-option-remaining {
  font-size: $font-size-caption;
  color: $text-secondary;
}

.card-option-applicable {
  font-size: $font-size-tiny;
  color: $text-tertiary;
}

.card-option-reason {
  font-size: $font-size-tiny;
  color: $error-color;
  margin-top: 4rpx;
}

.card-option-type {
  flex-shrink: 0;
}

.type-badge {
  padding: 4rpx 16rpx;
  border-radius: $radius-full;
  font-size: $font-size-tiny;
  font-weight: $font-weight-medium;

  &.type-count {
    background: linear-gradient(135deg, rgba(255, 236, 210, 0.6), rgba(252, 182, 159, 0.6));
    color: #c97a5e;
  }

  &.type-period {
    background: linear-gradient(135deg, rgba(168, 237, 234, 0.6), rgba(254, 214, 227, 0.6));
    color: #6ba3a0;
  }

  &.type-unlimited {
    background: linear-gradient(135deg, rgba(210, 153, 194, 0.6), rgba(254, 249, 215, 0.6));
    color: #9b6b8a;
  }
}

.selector-footer {
  padding-top: $space-sm;
  border-top: 1rpx solid $divider-color;
}

.confirm-btn-small {
  width: 100%;
  height: 88rpx;
  border-radius: $radius-2xl;
  border: none;
  background: $primary-gradient;
  color: #fff;
  font-size: $font-size-body;
  font-weight: $font-weight-medium;
  box-shadow: $shadow-button;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  margin: 0;

  &::after {
    border: none;
  }

  &[disabled] {
    background: $bg-tertiary;
    color: $text-disabled;
    box-shadow: none;
  }

  &:active {
    transform: scale(0.96);
  }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}
</style>