<template>
  <view class="detail-container">
    <view v-if="loading" class="loading-wrapper">
      <AppLoading />
    </view>

    <view v-else-if="!card" class="empty-wrapper">
      <AppEmpty text="会员卡不存在" />
    </view>

    <view v-else class="detail-content">
      <!-- 会员卡卡片 -->
      <view class="card-wrapper">
        <view class="membership-card" :class="getCardBgClass(card.status)">
          <!-- 卡片头部 -->
          <view class="card-header">
            <view class="card-type-badge">
              <text class="badge-text">{{ getCardTypeText(card.card_type) }}</text>
            </view>
            <view class="card-status-tag">
              <text class="status-text">{{ getStatusText(card.status) }}</text>
            </view>
          </view>

          <!-- 卡名 -->
          <text class="card-name">{{ card.product_name || '会员卡' }}</text>

          <!-- 次卡：显示剩余次数 -->
          <view v-if="card.card_type === 'count'" class="card-usage">
            <view class="usage-row">
              <view class="usage-main">
                <text class="usage-label">剩余</text>
                <text class="usage-value">{{ card.remaining_credits ?? 0 }}</text>
                <text class="usage-total">/{{ card.total_credits }}</text>
              </view>
              <view class="usage-sub">
                <text class="usage-sub-text">已用 {{ card.used_credits }} 次</text>
              </view>
            </view>
          </view>

          <!-- 期卡：显示有效天数 -->
          <view v-if="card.card_type === 'period'" class="card-valid-days">
            <view class="usage-row">
              <view class="usage-main">
                <text class="usage-value">{{ getValidDays(card) }}</text>
                <text class="usage-label">天</text>
              </view>
              <view class="usage-sub">
                <text class="usage-sub-text">
                  {{ formatDateShort(card.valid_from) }} - {{ formatDateShort(card.expire_at) }}
                </text>
              </view>
            </view>
          </view>

          <!-- 无限卡 -->
          <view v-if="card.card_type === 'unlimited'" class="card-unlimited">
            <text class="unlimited-text">不限次使用</text>
          </view>
        </view>
      </view>

      <!-- 详细信息 -->
      <view class="info-section">
        <view class="section-header">
          <view class="section-line"></view>
          <text class="section-title">详细信息</text>
        </view>

        <view class="info-card">
          <view class="info-row">
            <text class="info-label">生效时间</text>
            <text class="info-value">{{ card.valid_from ? formatDate(card.valid_from) : '未激活' }}</text>
          </view>
          <view class="info-divider"></view>
          <view class="info-row">
            <text class="info-label">过期时间</text>
            <text class="info-value" :class="{ 'value-warning': isExpiringSoon }">
              {{ card.expire_at ? formatDate(card.expire_at) : '-' }}
            </text>
          </view>
          <view v-if="card.max_weekly_usage" class="info-divider"></view>
          <view v-if="card.max_weekly_usage" class="info-row">
            <text class="info-label">每周限用</text>
            <text class="info-value">{{ card.max_weekly_usage }} 次/周</text>
          </view>
        </view>
      </view>

      <!-- 冻结信息 -->
      <view v-if="card.status === 3" class="info-section">
        <view class="section-header">
          <view class="section-line"></view>
          <text class="section-title">冻结信息</text>
        </view>

        <view class="info-card">
          <view class="info-row">
            <text class="info-label">冻结时间</text>
            <text class="info-value">{{ card.frozen_at ? formatDate(card.frozen_at) : '-' }}</text>
          </view>
          <view class="info-divider"></view>
          <view class="info-row">
            <text class="info-label">冻结到期</text>
            <text class="info-value">{{ card.frozen_until ? formatDate(card.frozen_until) : '-' }}</text>
          </view>
          <view class="info-divider"></view>
          <view class="info-row">
            <text class="info-label">已冻结时长</text>
            <text class="info-value">{{ getFrozenDuration(card) }}</text>
          </view>
          <view class="info-divider"></view>
          <view class="info-row">
            <text class="info-label">剩余冻结天数</text>
            <text class="info-value value-warning">{{ getFrozenRemainingDays(card) }} 天</text>
          </view>
          <view class="info-divider"></view>
          <view class="info-row">
            <text class="info-label">冻结原因</text>
            <text class="info-value">{{ card.frozen_reason || '-' }}</text>
          </view>
        </view>
      </view>

      <!-- 操作按钮 -->
      <view class="action-section">
        <!-- 未激活状态 -->
        <view v-if="card.status === 0" class="action-btn primary-btn" @tap="handleActivate">
          <text class="btn-text">立即激活</text>
        </view>

        <!-- 冻结到期后可提前激活 -->
        <view v-if="card.status === 3 && canStudentUnfreeze" class="action-btn primary-btn" @tap="handleUnfreeze">
          <text class="btn-text">提前激活</text>
        </view>

        <!-- 冻结中提示 -->
        <view v-if="card.status === 3 && !canStudentUnfreeze" class="frozen-tip-box">
          <text class="frozen-tip-text">冻结中，剩余 {{ getFrozenRemainingDays(card) }} 天后可激活</text>
        </view>

        <!-- 流水记录入口 -->
        <view class="action-btn secondary-btn" @tap="goToTransactions">
          <text class="btn-text">查看流水记录</text>
          <text class="btn-arrow">›</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { membershipApi } from '@/api'
import { checkLogin } from '@/utils/auth'
import AppLoading from '@/components/AppLoading.vue'
import AppEmpty from '@/components/AppEmpty.vue'
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
  max_weekly_usage: number | null
  applicable_course_ids: number[] | null
  created_at: string
  updated_at: string
}

const cardId = ref<number>(0)
const card = ref<MembershipCard | null>(null)
const loading = ref(true)

onMounted(() => {
  if (!checkLogin('student')) return

  const pages = getCurrentPages()
  const currentPage = pages[pages.length - 1] as any
  const options = currentPage.options || {}
  cardId.value = parseInt(options.cardId) || 0

  if (cardId.value) {
    loadCardDetail()
  }
})

const loadCardDetail = async () => {
  try {
    loading.value = true
    const res = await membershipApi.getCardDetail(cardId.value)
    card.value = res?.data as any
  } catch (error) {
    console.error('加载会员卡详情失败:', error)
    uni.showToast({ title: '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

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

const getCardBgClass = (status: number) => {
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

const getCardTypeText = (type: string) => {
  const map: Record<string, string> = {
    count: '次卡',
    period: '时效卡',
    unlimited: '无限卡'
  }
  return map[type] || type
}

const isExpiringSoon = computed(() => {
  if (!card.value?.expire_at) return false
  const now = new Date()
  const expireAt = new Date(card.value.expire_at)
  const diffMs = expireAt.getTime() - now.getTime()
  const days = Math.ceil(diffMs / (1000 * 60 * 60 * 24))
  return days > 0 && days <= 7
})

const canStudentUnfreeze = computed(() => {
  if (!card.value?.frozen_until) return false
  const now = new Date()
  const frozenUntil = new Date(card.value.frozen_until)
  return frozenUntil <= now
})

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hours = String(d.getHours()).padStart(2, '0')
  const minutes = String(d.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}`
}

const formatDateShort = (dateStr: string | null) => {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const getFrozenDuration = (card: MembershipCard) => {
  if (!card.frozen_at) return '-'
  const frozenAt = new Date(card.frozen_at)
  const now = new Date()
  const diffMs = now.getTime() - frozenAt.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
  if (diffDays === 0) return '不足1天'
  return `${diffDays} 天`
}

const getFrozenRemainingDays = (card: MembershipCard) => {
  if (!card.frozen_until) return 0
  const now = new Date()
  const frozenUntil = new Date(card.frozen_until)
  const diffMs = frozenUntil.getTime() - now.getTime()
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24))
  return Math.max(0, diffDays)
}

const handleActivate = () => {
  uni.showModal({
    title: '激活确认',
    content: `确定要激活「${card.value?.product_name || '会员卡'}」吗？激活后有效期开始计算。`,
    success: async (res) => {
      if (!res.confirm) return
      try {
        uni.showLoading({ title: '激活中...' })
        await membershipApi.activateCard(card.value!.id)
        uni.hideLoading()
        uni.showToast({ title: '激活成功', icon: 'success' })
        loadCardDetail()
      } catch (error: any) {
        uni.hideLoading()
        uni.showToast({ title: error?.response?.data?.msg || '激活失败', icon: 'none' })
      }
    }
  })
}

const handleUnfreeze = () => {
  uni.showModal({
    title: '提前激活',
    content: `确定要提前激活会员卡吗？激活后冻结状态将清除，有效期不再顺延。`,
    success: async (res) => {
      if (!res.confirm) return
      try {
        uni.showLoading({ title: '激活中...' })
        await membershipApi.activateCard(card.value!.id)
        uni.hideLoading()
        uni.showToast({ title: '激活成功', icon: 'success' })
        loadCardDetail()
      } catch (error: any) {
        uni.hideLoading()
        uni.showToast({ title: error?.response?.data?.msg || '激活失败', icon: 'none' })
      }
    }
  })
}

const goToTransactions = () => {
  navigateTo({
    url: `/pages/student/membership/transactions?cardId=${card.value!.id}&cardName=${encodeURIComponent(card.value?.product_name || '会员卡')}`
  })
}
</script>

<style lang="scss">
.detail-container {
  min-height: 100vh;
  background: #f5f3ef;
}

.loading-wrapper,
.empty-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 60vh;
}

.detail-content {
  padding: $space-md;
}

// 会员卡卡片
.card-wrapper {
  margin-bottom: $space-lg;
}

.membership-card {
  border-radius: $radius-lg;
  padding: $space-lg;
  color: #fff;
}

.card-active {
  background: linear-gradient(135deg, #2C2C2C 0%, #3D3D3D 50%, #4A4A4A 100%);
}

.card-frozen {
  background: linear-gradient(135deg, #4A3F35 0%, #5C4D3C 100%);
}

.card-expired {
  background: linear-gradient(135deg, #6B6B6B 0%, #8A8A8A 100%);
}

.card-inactive {
  background: linear-gradient(135deg, #8A8A8A 0%, #A5A5A5 100%);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: $space-md;
}

.card-type-badge {
  padding: 6rpx $space-sm;
  background: rgba(255, 255, 255, 0.2);
  border-radius: $radius-sm;

  .badge-text {
    font-size: $font-size-caption;
    color: rgba(255, 255, 255, 0.9);
  }
}

.card-status-tag {
  padding: 6rpx $space-sm;
  background: rgba(255, 255, 255, 0.15);
  border-radius: $radius-sm;

  .status-text {
    font-size: $font-size-caption;
    color: rgba(255, 255, 255, 0.8);
  }
}

.card-name {
  display: block;
  font-size: $font-size-h3;
  font-weight: $font-weight-bold;
  color: #fff;
  margin-bottom: $space-md;
}

// 次卡使用信息
.card-usage {
  .usage-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .usage-main {
    display: flex;
    align-items: baseline;
    gap: 4rpx;

    .usage-label {
      font-size: $font-size-body_sm;
      color: rgba(255, 255, 255, 0.7);
    }

    .usage-value {
      font-size: $font-size-h2;
      font-weight: $font-weight-bold;
      color: #fff;
    }

    .usage-total {
      font-size: $font-size-body;
      color: rgba(255, 255, 255, 0.6);
    }
  }

  .usage-sub {
    .usage-sub-text {
      font-size: $font-size-caption;
      color: rgba(255, 255, 255, 0.5);
    }
  }
}

// 期卡有效天数
.card-valid-days {
  .usage-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .usage-main {
    display: flex;
    align-items: baseline;
    gap: 4rpx;

    .usage-value {
      font-size: $font-size-h2;
      font-weight: $font-weight-bold;
      color: #fff;
    }

    .usage-label {
      font-size: $font-size-body;
      color: rgba(255, 255, 255, 0.7);
    }
  }

  .usage-sub {
    .usage-sub-text {
      font-size: $font-size-caption;
      color: rgba(255, 255, 255, 0.5);
    }
  }
}

// 无限卡
.card-unlimited {
  .unlimited-text {
    font-size: $font-size-body;
    color: rgba(255, 255, 255, 0.8);
  }
}

// 详细信息区域
.info-section {
  margin-bottom: $space-lg;
}

.section-header {
  display: flex;
  align-items: center;
  gap: $space-xs;
  margin-bottom: $space-sm;
}

.section-line {
  width: 6rpx;
  height: 28rpx;
  background: $primary-solid;
  border-radius: 3rpx;
}

.section-title {
  font-size: $font-size-body;
  font-weight: $font-weight-bold;
  color: $text-primary;
}

.info-card {
  background: #fff;
  border-radius: $radius-md;
  overflow: hidden;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: $space-md;
}

.info-divider {
  height: 1rpx;
  background: $border-light;
  margin: 0 $space-md;
}

.info-label {
  font-size: $font-size-body_sm;
  color: $text-secondary;
}

.info-value {
  font-size: $font-size-body_sm;
  color: $text-primary;

  &.value-warning {
    color: #c0392b;
  }
}

// 操作按钮
.action-section {
  padding: 0 $space-xs;
}

.action-btn {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 88rpx;
  border-radius: $radius-md;
  margin-bottom: $space-md;

  &:active {
    opacity: 0.8;
  }
}

.primary-btn {
  background: linear-gradient(135deg, #d4a96a 0%, #e8c99b 100%);

  .btn-text {
    font-size: $font-size-body;
    font-weight: $font-weight-bold;
    color: #fff;
  }
}

.secondary-btn {
  background: #fff;
  border: 1rpx solid $border-normal;

  .btn-text {
    font-size: $font-size-body;
    color: $text-primary;
  }

  .btn-arrow {
    margin-left: $space-2xs;
    font-size: $font-size-body;
    color: $text-secondary;
  }
}

.frozen-tip-box {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 88rpx;
  background: $bg-secondary;
  border-radius: $radius-md;
  margin-bottom: $space-md;

  .frozen-tip-text {
    font-size: $font-size-body_sm;
    color: $text-secondary;
  }
}
</style>