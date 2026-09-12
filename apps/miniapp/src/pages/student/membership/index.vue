<template>
  <view class="membership_container">
    <!-- 顶部筛选标签（固定） -->
    <view class="filter-tabs">
      <view
        class="filter-tab"
        :class="{ 'tab-active': selectedTab === 'valid' }"
        @tap="selectedTab = 'valid'"
      >
        <text class="tab-text">有效卡</text>
      </view>
      <view
        class="filter-tab"
        :class="{ 'tab-active': selectedTab === 'invalid' }"
        @tap="selectedTab = 'invalid'"
      >
        <text class="tab-text">无效卡</text>
      </view>
    </view>

    <!-- 可滚动区域：会员卡列表 -->
    <scroll-view scroll-y class="cards-scroll" :show-scrollbar="false">
      <!-- 有效卡列表 -->
      <view v-if="selectedTab === 'valid'" class="cards-section">
        <!-- 空状态 -->
        <view v-if="validCards.length === 0" class="empty-state">
          <view class="empty-icon-wrapper">
            <text class="empty-icon">💳</text>
          </view>
          <text class="empty-title">暂无有效会员卡</text>
          <text class="empty-desc">请联系管理员办理会员卡</text>
        </view>
        <template v-else>
        <!-- 使用中的卡 -->
        <view v-if="activeCards.length > 0" class="active-cards-section">
          <view
            v-for="card in activeCards"
            :key="card.id"
            class="active-card-banner"
            @tap="goToDetail(card)"
          >
            <view class="banner-bg"></view>
            <view class="banner-content">
              <!-- 头部 -->
              <view class="banner-header">
                <view class="banner-title-row">
                  <text class="banner-icon"></text>
                  <text class="banner-name">{{ card.product_name || '会员卡' }}</text>
                  <view class="banner-status-badge">
                    <text class="badge-dot"></text>
                    <text class="badge-text">使用中</text>
                  </view>
                </view>
              </view>

              <!-- 次卡：剩余次数 -->
              <view v-if="card.card_type === 'count'" class="banner-usage">
                <view class="usage-left">
                  <text class="usage-value">{{ card.remaining_credits ?? 0 }}</text>
                  <text class="usage-total">/{{ card.total_credits }} 次</text>
                </view>
                <view class="usage-right">
                  <text class="expiry-label">有效期至</text>
                  <text class="expiry-date">{{ formatDateShort(card.expire_at) }}</text>
                </view>
              </view>

              <!-- 期卡：有效天数 -->
              <view v-if="card.card_type === 'period'" class="banner-usage">
                <view class="usage-left">
                  <text class="usage-value">{{ getValidDays(card) }}</text>
                  <text class="usage-total">天</text>
                </view>
                <view class="usage-right">
                  <text class="expiry-label">有效期至</text>
                  <text class="expiry-date">{{ formatDateShort(card.expire_at) }}</text>
                </view>
              </view>

              <!-- 无限卡 -->
              <view v-if="card.card_type === 'unlimited'" class="banner-usage">
                <view class="usage-left">
                  <text class="usage-value">不限次</text>
                </view>
                <view class="usage-right">
                  <text class="expiry-label">永久有效</text>
                </view>
              </view>
            </view>
            <!-- 装饰图标 -->
            <view class="banner-decoration">
              <text class="deco-icon">💃</text>
            </view>
          </view>
        </view>

        <!-- 未激活/冻结的卡 -->
        <view class="inactive-cards-section">
          <view
            v-for="card in pendingCards"
            :key="card.id"
            class="card-item"
            :class="getCardStatusClass(card.status)"
            @tap="goToDetail(card)"
          >
            <!-- 左侧图标 -->
            <view class="card-icon-wrapper" :class="getCardIconClass(card)">
              <text class="card-icon">{{ getCardIcon(card) }}</text>
            </view>

            <!-- 卡片内容 -->
            <view class="card-content">
              <!-- 头部 -->
              <view class="card-header">
                <view class="card-title-row">
                  <text class="card-name">{{ card.product_name || '会员卡' }}</text>
                  <view class="card-type-badge" :class="getCardTypeBadgeClass(card)">
                    <text class="type-text">{{ getCardTypeLabel(card) }}</text>
                  </view>
                </view>
                <text class="card-arrow">›</text>
              </view>

              <!-- 使用信息 -->
              <view class="card-info">
                <!-- 次卡 -->
                <view v-if="card.card_type === 'count'" class="info-row info-row-single">
                  <view class="info-main">
                    <text class="info-value">{{ card.remaining_credits ?? 0 }}</text>
                    <text class="info-total">/{{ card.total_credits }} 次</text>
                  </view>
                  <view class="info-sub-inline">
                    <text class="info-sub-value">{{ formatDateShort(card.valid_from) }} - {{ formatDateShort(card.expire_at) }}</text>
                  </view>
                </view>
                <!-- 期卡 -->
                <view v-if="card.card_type === 'period'" class="info-row info-row-single">
                  <view class="info-main">
                    <text class="info-value">{{ getValidDays(card) }}</text>
                    <text class="info-label">天</text>
                  </view>
                  <view class="info-sub-inline">
                    <text class="info-sub-value">{{ formatDateShort(card.valid_from) }} - {{ formatDateShort(card.expire_at) }}</text>
                  </view>
                </view>
                <!-- 无限卡 -->
                <view v-if="card.card_type === 'unlimited'" class="info-row info-row-single">
                  <text class="info-unlimited">不限次使用</text>
                </view>
              </view>

              <!-- 虚线分隔 -->
              <view class="card-divider"></view>

              <!-- 底部状态栏 -->
              <view class="card-footer">
                <view class="footer-left">
                  <text class="status-text" :class="getStatusTextColor(card.status)">
                    {{ getStatusText(card.status) }}
                  </text>
                </view>
                <view class="footer-right">
                  <!-- 未激活：显示激活按钮 -->
                  <button 
                    v-if="card.status === 0" 
                    class="activate-btn" 
                    @tap.stop="handleActivate(card)"
                  >
                    立即激活
                  </button>
                  <!-- 冻结到期可激活 -->
                  <button 
                    v-else-if="card.status === 3 && canStudentUnfreeze(card)" 
                    class="activate-btn" 
                    @tap.stop="handleUnfreeze(card)"
                  >
                    提前激活
                  </button>
                  <!-- 冻结中 -->
                  <text 
                    v-else-if="card.status === 3 && !canStudentUnfreeze(card)" 
                    class="frozen-text"
                  >
                    冻结至 {{ formatDateShort(card.frozen_until) }}
                  </text>
                </view>
              </view>
            </view>
          </view>
        </view>
        </template>
      </view>

      <!-- 无效卡列表（过期卡） -->
      <view v-if="selectedTab === 'invalid'" class="cards-section">
        <!-- 空状态 -->
        <view v-if="invalidCards.length === 0" class="empty-state">
          <view class="empty-icon-wrapper">
            <text class="empty-icon">📭</text>
          </view>
          <text class="empty-title">暂无无效卡</text>
          <text class="empty-desc">所有会员卡均在有效期内</text>
        </view>
        <template v-else>
        <view
          v-for="card in invalidCards"
          :key="card.id"
          class="card-item card-expired"
          @tap="goToDetail(card)"
        >
          <!-- 左侧图标 -->
          <view class="card-icon-wrapper" :class="getCardIconClass(card)">
            <text class="card-icon">{{ getCardIcon(card) }}</text>
          </view>

          <!-- 卡片内容 -->
          <view class="card-content">
            <!-- 头部 -->
            <view class="card-header">
              <view class="card-title-row">
                <text class="card-name">{{ card.product_name || '会员卡' }}</text>
                <!-- <view class="card-type-badge" :class="getCardTypeBadgeClass(card)">
                  <text class="type-text">{{ getCardTypeLabel(card) }}</text>
                </view> -->
              </view>
              <text class="card-arrow">›</text>
            </view>

            <!-- 使用信息 -->
            <view class="card-info">
              <!-- 次卡 -->
              <view v-if="card.card_type === 'count'" class="info-row info-row-single">
                <view class="info-main">
                  <text class="info-value">{{ card.remaining_credits ?? 0 }}</text>
                  <text class="info-total">/{{ card.total_credits }} 次</text>
                </view>
                <view class="info-sub-inline">
                  <text class="info-sub-value">{{ formatDateShort(card.valid_from) }} - {{ formatDateShort(card.expire_at) }}</text>
                </view>
              </view>
              <!-- 期卡 -->
              <view v-if="card.card_type === 'period'" class="info-row info-row-single">
                <view class="info-main">
                  <text class="info-value">{{ getValidDays(card) }}</text>
                  <text class="info-label">天</text>
                </view>
                <view class="info-sub-inline">
                  <text class="info-sub-value">{{ formatDateShort(card.valid_from) }} - {{ formatDateShort(card.expire_at) }}</text>
                </view>
              </view>
              <!-- 无限卡 -->
              <view v-if="card.card_type === 'unlimited'" class="info-row info-row-single">
                <text class="info-unlimited">不限次使用</text>
              </view>
            </view>

            <!-- 虚线分隔 -->
            <view class="card-divider"></view>

            <!-- 底部状态栏 -->
            <view class="card-footer">
              <view class="footer-left">
                <text class="status-text text-expired">
                  已过期
                </text>
              </view>
            </view>
          </view>
        </view>
        </template>
      </view>
    </scroll-view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { membershipApi } from '@/api'
import { checkLogin } from '@/utils/auth'
import AppLoading from '@/components/AppLoading.vue'
import { navigateTo } from '@/utils/navigation'

interface MembershipCard {
  id: number
  product_name?: string
  card_type: string
  total_credits: number | null
  used_credits: number
  remaining_credits: number | null
  status: number
  expire_at: string | null
  valid_from: string | null
  frozen_at: string | null
  frozen_until: string | null
  frozen_reason: string | null
}

const cards = ref<MembershipCard[]>([])
const loading = ref(true)
const selectedTab = ref('valid')

// 使用中的卡列表
const activeCards = computed(() => {
  return cards.value.filter(c => c.status === 1)
})

// 待激活/冻结的卡（有效但未使用）
const pendingCards = computed(() => {
  return cards.value.filter(c => c.status === 0 || c.status === 3)
})

// 有效卡（未过期的所有卡）
const validCards = computed(() => {
  return cards.value.filter(c => c.status !== 2)
})

// 无效卡（过期卡）
const invalidCards = computed(() => {
  return cards.value.filter(c => c.status === 2)
})

// 获取期卡有效天数（从生效到过期之间的总天数）
const getValidDays = (card: MembershipCard) => {
  if (!card?.valid_from || !card?.expire_at) return 0
  const validFrom = new Date(card.valid_from)
  const expireAt = new Date(card.expire_at)
  // 只比较日期部分，忽略时间
  const fromDay = new Date(validFrom.getFullYear(), validFrom.getMonth(), validFrom.getDate())
  const toDay = new Date(expireAt.getFullYear(), expireAt.getMonth(), expireAt.getDate())
  const diffMs = toDay.getTime() - fromDay.getTime()
  if (diffMs <= 0) return 0
  return Math.round(diffMs / (1000 * 60 * 60 * 24))
}

// 获取卡片图标
const getCardIcon = (card: MembershipCard) => {
  const iconMap: Record<string, string> = {
    count: '🎫',
    period: '📅',
    unlimited: '♾️'
  }
  return iconMap[card.card_type] || '💳'
}

// 获取卡片图标样式类
const getCardIconClass = (card: MembershipCard) => {
  const classMap: Record<string, string> = {
    count: 'icon-count',
    period: 'icon-period',
    unlimited: 'icon-unlimited'
  }
  return classMap[card.card_type] || 'icon-default'
}

// 获取卡类型标签样式类
const getCardTypeBadgeClass = (card: MembershipCard) => {
  const classMap: Record<string, string> = {
    count: 'badge-count',
    period: 'badge-period',
    unlimited: 'badge-unlimited'
  }
  return classMap[card.card_type] || 'badge-default'
}

onMounted(() => {
  if (!checkLogin('student')) return
  loadCards()
})

const loadCards = async () => {
  try {
    loading.value = true
    const res = await membershipApi.getMyCards()
    const responseData = res?.data as any
    if (responseData?.items && Array.isArray(responseData.items)) {
      cards.value = responseData.items
    } else if (Array.isArray(responseData)) {
      cards.value = responseData
    } else if (responseData) {
      cards.value = [responseData]
    }
  } catch (error) {
    console.error('加载会员卡失败:', error)
    uni.showToast({ title: '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

const getCardStatusClass = (status: number) => {
  const map: Record<number, string> = {
    0: 'card-inactive',
    1: 'card-active',
    2: 'card-expired',
    3: 'card-frozen'
  }
  return map[status] || 'card-inactive'
}

const getStatusText = (status: number) => {
  const map: Record<number, string> = {
    0: '未激活',
    1: '使用中',
    2: '已过期',
    3: '已冻结'
  }
  return map[status] || '未知'
}

const getStatusTextColor = (status: number) => {
  const map: Record<number, string> = {
    0: 'text-inactive',
    1: 'text-active',
    2: 'text-expired',
    3: 'text-frozen'
  }
  return map[status] || 'text-inactive'
}

const getCardTypeLabel = (card: MembershipCard) => {
  const typeMap: Record<string, string> = {
    count: '次卡',
    period: '时效卡',
    unlimited: '无限卡'
  }
  return typeMap[card.card_type] || card.card_type
}

const formatDateShort = (dateStr: string | null) => {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const getFrozenRemainingDays = (card: MembershipCard) => {
  if (!card.frozen_until) return 0
  const now = new Date()
  const frozenUntil = new Date(card.frozen_until)
  const diffMs = frozenUntil.getTime() - now.getTime()
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24))
  return Math.max(0, diffDays)
}

const canStudentUnfreeze = (card: MembershipCard) => {
  if (!card.frozen_until) return false
  const now = new Date()
  const frozenUntil = new Date(card.frozen_until)
  return frozenUntil <= now
}

const goToDetail = (card: MembershipCard) => {
  navigateTo({
    url: `/pages/student/membership/detail?cardId=${card.id}`
  })
}

const goToTransactions = (card: MembershipCard) => {
  navigateTo({
    url: `/pages/student/membership/transactions?cardId=${card.id}&cardName=${encodeURIComponent(card.product_name || '会员卡')}`
  })
}

const handleActivate = async (card: MembershipCard) => {
  uni.showModal({
    title: '激活确认',
    content: `确定要激活「${card.product_name || '会员卡'}」吗？激活后有效期开始计算。`,
    success: async (res) => {
      if (!res.confirm) return
      try {
        uni.showLoading({ title: '激活中...' })
        await membershipApi.activateCard(card.id)
        uni.hideLoading()
        uni.showToast({ title: '激活成功', icon: 'success' })
        loadCards()
      } catch (error: any) {
        uni.hideLoading()
        uni.showToast({ title: error?.response?.data?.msg || '激活失败', icon: 'none' })
      }
    }
  })
}

const handleUnfreeze = async (card: MembershipCard) => {
  uni.showModal({
    title: '提前激活',
    content: `确定要提前激活会员卡吗？激活后冻结状态将清除，有效期不再顺延。`,
    success: async (res) => {
      if (!res.confirm) return
      try {
        uni.showLoading({ title: '激活中...' })
        await membershipApi.activateCard(card.id)
        uni.hideLoading()
        uni.showToast({ title: '激活成功', icon: 'success' })
        loadCards()
      } catch (error: any) {
        uni.hideLoading()
        uni.showToast({ title: error?.response?.data?.msg || '激活失败', icon: 'none' })
      }
    }
  })
}
</script>

<style lang="scss">
.membership_container {
  @include page-container;
  background: $bg-secondary;
  display: flex;
  flex-direction: column;
  height: 100vh;
}

// ===== 顶部筛选标签（固定） =====
.filter-tabs {
  display: flex;
  gap: $space-sm;
  padding: $space-sm $space-md;
  background: $bg-secondary;
  flex-shrink: 0;
}

.filter-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: $space-xs 0;
  background: #fff;
  border-radius: 50rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.04);
  transition: all 0.2s ease;

  .tab-text {
    font-size: $font-size-body_sm;
    color: $text-secondary;
    font-weight: $font-weight-medium;
  }

  &.tab-active {
    background: linear-gradient(135deg, #d4b87a 0%, #c9a96e 100%);
    box-shadow: 0 4rpx 16rpx rgba(201, 169, 110, 0.3);

    .tab-text {
      color: #fff;
      font-weight: $font-weight-bold;
    }
  }
}

// ===== 可滚动区域 =====
.cards-scroll {
  flex: 1;
  height: 0;
  padding: 0 $space-md;
  padding-bottom: 40rpx;
  box-sizing: border-box;
}

.loading-wrapper,
.empty-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 60vh;
}

.empty-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: $space-md;

  .empty-icon {
    font-size: 120rpx;
    opacity: 0.3;
  }

  .empty-text {
    font-size: $font-size-body;
    color: $text-secondary;
  }

  .empty-hint {
    font-size: $font-size-body_sm;
    color: $text-tertiary;
  }
}

// ===== 顶部使用中的会员卡 =====
.active-cards-section {
  display: flex;
  flex-direction: column;
  gap: $space-sm;
}

.active-card-banner {
  position: relative;
  border-radius: $radius-lg;
  overflow: hidden;
  background: linear-gradient(135deg, #f5e6c8 0%, #f0d9a8 50%, #e8cc90 100%);
  box-shadow: 0 4rpx 16rpx rgba(180, 140, 60, 0.15);

  .banner-bg {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: 
      radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.3) 0%, transparent 50%),
      radial-gradient(circle at 20% 80%, rgba(255, 255, 255, 0.15) 0%, transparent 40%);
  }

  .banner-content {
    position: relative;
    z-index: 1;
    padding: $space-sm $space-md;
  }

  .banner-header {
    margin-bottom: $space-xs;
  }

  .banner-title-row {
    display: flex;
    align-items: center;
    gap: $space-xs;
    margin-bottom: 4rpx;
  }

  .banner-icon {
    font-size: $font-size-caption;
  }

  .banner-name {
    font-size: $font-size-body;
    font-weight: $font-weight-bold;
    color: #5a4a2a;
  }

  .banner-status-badge {
    display: flex;
    align-items: center;
    gap: 2rpx;
    padding: 2rpx $space-xs;
    background: rgba(76, 175, 80, 0.15);
    border-radius: $radius-sm;

    .badge-dot {
      width: 6rpx;
      height: 6rpx;
      border-radius: 50%;
      background: #4caf50;
    }

    .badge-text {
      font-size: $font-size-caption;
      color: #4caf50;
      font-weight: $font-weight-medium;
    }
  }

  .banner-type {
    font-size: $font-size-caption;
    color: rgba(90, 74, 42, 0.6);
  }

  .banner-usage {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
  }

  .usage-left {
    display: flex;
    align-items: baseline;
    gap: 2rpx;

    .usage-label {
      font-size: $font-size-caption;
      color: rgba(90, 74, 42, 0.6);
    }

    .usage-value {
      font-size: $font-size-h3;
      font-weight: $font-weight-bold;
      color: #5a4a2a;
    }

    .usage-total {
      font-size: $font-size-body_sm;
      color: rgba(90, 74, 42, 0.6);
    }
  }

  .usage-right {
    text-align: right;

    .expiry-label {
      display: block;
      font-size: $font-size-caption;
      color: rgba(90, 74, 42, 0.5);
      margin-bottom: 2rpx;
    }

    .expiry-date {
      font-size: $font-size-caption;
      color: rgba(90, 74, 42, 0.7);
    }
  }

  // 装饰
  .banner-decoration {
    position: absolute;
    top: $space-sm;
    right: $space-sm;
    width: 80rpx;
    height: 80rpx;
    opacity: 0.12;

    .deco-icon {
      font-size: 80rpx;
    }
  }
}

// ===== 卡片区域 =====
.cards-section {
  display: flex;
  flex-direction: column;
  gap: $space-sm;
}

// 空状态
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 100rpx $space-md 80rpx;
  gap: $space-md;

  .empty-icon-wrapper {
    width: 160rpx;
    height: 160rpx;
    border-radius: 50%;
    background: $bg-secondary;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: $space-sm;
  }

  .empty-icon {
    font-size: 80rpx;
    opacity: 0.5;
  }

  .empty-title {
    font-size: $font-size-h4;
    font-weight: $font-weight-medium;
    color: $text-secondary;
  }

  .empty-desc {
    font-size: $font-size-body_sm;
    color: $text-tertiary;
  }
}

// ===== 顶部使用中的会员卡 =====
.active-cards-section {
  display: flex;
  flex-direction: column;
  gap: $space-md;
}

.active-card-banner {
  position: relative;
  border-radius: $radius-lg;
  overflow: hidden;
  background: linear-gradient(135deg, #f5e6c8 0%, #f0d9a8 50%, #e8cc90 100%);
  box-shadow: 0 8rpx 32rpx rgba(180, 140, 60, 0.2);
}

// ===== 未激活/冻结卡区域 =====
.inactive-cards-section {
  display: flex;
  flex-direction: column;
  gap: $space-sm;
}

.card-item {
  display: flex;
  align-items: flex-start;
  gap: $space-sm;
  padding: $space-md;
  background: #fff;
  border-radius: $radius-lg;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.04);
  transition: all 0.2s ease;

  &:active {
    transform: scale(0.98);
  }

  // 未激活
  &.card-inactive {
    opacity: 0.75;
  }

  // 已过期
  &.card-expired {
    opacity: 0.5;
  }

  // 已冻结
  &.card-frozen {
    opacity: 0.6;
  }
}

// 卡片图标
.card-icon-wrapper {
  flex-shrink: 0;
  width: 72rpx;
  height: 72rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;

  .card-icon {
    font-size: 36rpx;
  }

  &.icon-count {
    background: rgba(156, 39, 176, 0.1);
  }

  &.icon-period {
    background: rgba(33, 150, 243, 0.1);
  }

  &.icon-unlimited {
    background: rgba(76, 175, 80, 0.1);
  }

  &.icon-default {
    background: $bg-secondary;
  }
}

// 卡片内容
.card-content {
  flex: 1;
  min-width: 0;
}

// 卡片头部
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: $space-xs;
}

.card-title-row {
  display: flex;
  align-items: center;
  gap: $space-xs;
  flex: 1;
  min-width: 0;
}

.card-name {
  font-size: $font-size-h4;
  font-weight: $font-weight-bold;
  color: $text-primary;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-type-badge {
  flex-shrink: 0;
  padding: 2rpx $space-xs;
  border-radius: $radius-sm;

  .type-text {
    font-size: $font-size-caption;
  }

  &.badge-count {
    background: rgba(156, 39, 176, 0.1);
    .type-text { color: #9c27b0; }
  }

  &.badge-period {
    background: rgba(33, 150, 243, 0.1);
    .type-text { color: #2196f3; }
  }

  &.badge-unlimited {
    background: rgba(76, 175, 80, 0.1);
    .type-text { color: #4caf50; }
  }

  &.badge-default {
    background: $bg-secondary;
    .type-text { color: $text-secondary; }
  }
}

.card-arrow {
  flex-shrink: 0;
  font-size: $font-size-h3;
  color: $text-tertiary;
  margin-left: $space-xs;
}

// 使用信息
.card-info {
  margin-bottom: $space-sm;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 48rpx;
}

// 单行展示（对齐）
.info-row-single {
  align-items: center;
}

.info-main {
  display: flex;
  align-items: baseline;
  gap: 4rpx;

  .info-label {
    font-size: $font-size-body_sm;
    color: $text-secondary;
  }

  .info-value {
    font-size: $font-size-h3;
    font-weight: $font-weight-bold;
    color: #c0392b;
  }

  .info-total {
    font-size: $font-size-body_sm;
    color: $text-secondary;
  }
}

.info-sub {
  text-align: right;
  flex-shrink: 0;

  .info-sub-label {
    display: block;
    font-size: $font-size-caption;
    color: $text-tertiary;
    margin-bottom: 2rpx;
  }

  .info-sub-value {
    font-size: $font-size-caption;
    color: $text-secondary;
  }
}

// 单行内联展示
.info-sub-inline {
  display: flex;
  align-items: center;
  gap: $space-xs;
  flex-shrink: 0;

  .info-sub-label {
    font-size: $font-size-caption;
    color: $text-tertiary;
  }

  .info-sub-value {
    font-size: $font-size-caption;
    color: $text-secondary;
  }
}

// 虚线分隔
.card-divider {
  height: 1rpx;
  background: repeating-linear-gradient(
    to right,
    $border-light 0,
    $border-light 6rpx,
    transparent 6rpx,
    transparent 12rpx
  );
  margin: $space-sm 0;
}

.info-unlimited {
  font-size: $font-size-body_sm;
  color: #4caf50;
  font-weight: $font-weight-medium;
}

// 底部状态栏
.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.footer-left {
  .status-text {
    font-size: $font-size-body_sm;
    font-weight: $font-weight-medium;
  }

  .text-active {
    color: $primary-solid;
  }

  .text-inactive {
    color: $text-secondary;
  }

  .text-expired {
    color: $text-disabled;
  }

  .text-frozen {
    color: $accent-solid;
  }
}

.footer-right {
  display: flex;
  align-items: center;
}

.activate-btn {
  padding: 8rpx $space-md;
  font-size: $font-size-caption;
  color: $primary-solid;
  background: transparent;
  border: 1rpx solid $primary-solid;
  border-radius: $radius-sm;
  line-height: 1.5;

  &::after {
    border: none;
  }

  &:active {
    background: rgba($primary-solid, 0.05);
  }
}

.frozen-text {
  font-size: $font-size-caption;
  color: $text-secondary;
}
</style>