<template>
  <view class="transactions_container">

    <view v-if="loading && transactions.length === 0" class="loading-wrapper">
      <AppLoading />
    </view>

    <view v-else-if="transactions.length === 0" class="empty-wrapper">
      <AppEmpty text="暂无流水记录" />
    </view>

    <view v-else class="transactions-list">
      <view
        v-for="item in transactions"
        :key="item.id"
        class="transaction-item"
      >
        <view class="transaction-icon">
          <text>{{ getTransactionIcon(item.operation_type) }}</text>
        </view>
        <view class="transaction-content">
          <view class="transaction-header">
            <text class="transaction-type">{{ getTransactionTypeText(item.operation_type) }}</text>
            <text class="transaction-amount" :class="getAmountClass(item.operation_type)">
              {{ formatAmount(item.operation_type, item.change_amount) }}
            </text>
          </view>
          <view class="transaction-footer">
            <text class="transaction-time">{{ formatTime(item.created_at) }}</text>
            <text class="transaction-balance">余额: {{ item.balance_after }}</text>
          </view>
          <text v-if="item.remark" class="transaction-remark">{{ item.remark }}</text>
        </view>
      </view>

      <view v-if="hasMore && !loadingMore" class="load-more" @tap="loadMore">
        <text>加载更多</text>
      </view>
      <view v-if="loadingMore" class="loading-more">
        <AppLoading />
      </view>
      <view v-if="!hasMore && transactions.length > 0" class="no-more">
        <text>没有更多了</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { membershipApi } from '@/api'
import { checkLogin } from '@/utils/auth'
import AppNavbar from '@/components/AppNavbar.vue'
import AppLoading from '@/components/AppLoading.vue'
import AppEmpty from '@/components/AppEmpty.vue'

interface Transaction {
  id: number
  operation_type: string
  change_amount: number
  balance_after: number
  remark: string | null
  created_at: string
}

const cardId = ref<number>(0)
const cardName = ref('会员卡')
const transactions = ref<Transaction[]>([])
const loading = ref(true)
const loadingMore = ref(false)
const hasMore = ref(true)
const page = ref(1)
const pageSize = 20

onMounted(() => {
  if (!checkLogin('student')) return

  const pages = getCurrentPages()
  const currentPage = pages[pages.length - 1] as any
  const options = currentPage.options || {}
  cardId.value = parseInt(options.cardId) || 0
  cardName.value = decodeURIComponent(options.cardName || '会员卡')

  loadTransactions()
})

const loadTransactions = async () => {
  try {
    loading.value = true
    const res = await membershipApi.getTransactions({
      card_id: cardId.value,
      page: page.value,
      page_size: pageSize
    })

    const responseData = res?.data as any
    let items: Transaction[] = []

    if (responseData?.items && Array.isArray(responseData.items)) {
      items = responseData.items
      hasMore.value = items.length >= pageSize
    } else if (Array.isArray(responseData)) {
      items = responseData
      hasMore.value = items.length >= pageSize
    }

    transactions.value = items
  } catch (error) {
    console.error('加载流水失败:', error)
    uni.showToast({ title: '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

const loadMore = async () => {
  if (loadingMore.value || !hasMore.value) return

  try {
    loadingMore.value = true
    page.value++

    const res = await membershipApi.getTransactions({
      card_id: cardId.value,
      page: page.value,
      page_size: pageSize
    })

    const responseData = res?.data as any
    let items: Transaction[] = []

    if (responseData?.items && Array.isArray(responseData.items)) {
      items = responseData.items
      hasMore.value = items.length >= pageSize
    } else if (Array.isArray(responseData)) {
      items = responseData
      hasMore.value = items.length >= pageSize
    } else {
      hasMore.value = false
    }

    transactions.value = [...transactions.value, ...items]
  } catch (error) {
    console.error('加载更多流水失败:', error)
    page.value--
  } finally {
    loadingMore.value = false
  }
}

const getTransactionIcon = (type: string) => {
  const map: Record<string, string> = {
    deduct: '➖',
    restore: '➕',
    freeze: '❄️',
    unfreeze: '🔓',
    expire: '⏰',
    grant: '🎁'
  }
  return map[type] || '📝'
}

const getTransactionTypeText = (type: string) => {
  const map: Record<string, string> = {
    deduct: '约课扣次',
    restore: '取消恢复',
    freeze: '冻结',
    unfreeze: '解冻',
    expire: '过期',
    grant: '发放'
  }
  return map[type] || type
}

const getAmountClass = (type: string) => {
  if (type === 'deduct' || type === 'expire') return 'amount-negative'
  return 'amount-positive'
}

const formatAmount = (type: string, amount: number) => {
  if (type === 'deduct' || type === 'expire') {
    return `-${Math.abs(amount)}`
  }
  return `+${amount}`
}

const formatTime = (timeStr: string) => {
  if (!timeStr) return '-'
  const d = new Date(timeStr)
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hour = String(d.getHours()).padStart(2, '0')
  const minute = String(d.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:${minute}`
}
</script>

<style lang="scss">
.transactions_container {
  min-height: 100vh;
  background: $bg-secondary;
  padding-bottom: 40rpx;
}

.loading-wrapper,
.empty-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 60vh;
}

.transactions-list {
  padding: $space-lg;
}

.transaction-item {
  display: flex;
  gap: $space-md;
  padding: $space-md $space-lg;
  margin-bottom: $space-sm;
  background: $bg-elevated;
  border-radius: $radius-lg;
  box-shadow: $shadow-sm;

  &:active {
    background: $bg-secondary;
  }
}

.transaction-icon {
  font-size: 48rpx;
  width: 64rpx;
  height: 64rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.transaction-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: $space-xs;
}

.transaction-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.transaction-type {
  font-size: $font-size-body;
  font-weight: $font-weight-medium;
  color: $text-primary;
}

.transaction-amount {
  font-size: $font-size-h3;
  font-weight: $font-weight-bold;
}

.amount-positive {
  color: $success-color;
}

.amount-negative {
  color: $error-color;
}

.transaction-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.transaction-time {
  font-size: $font-size-caption;
  color: $text-tertiary;
}

.transaction-balance {
  font-size: $font-size-caption;
  color: $text-secondary;
}

.transaction-remark {
  font-size: $font-size-caption;
  color: $text-tertiary;
  padding-top: $space-xs;
  border-top: 1rpx solid $border-light;
}

.load-more,
.no-more {
  text-align: center;
  padding: $space-lg 0;
  font-size: $font-size-body_sm;
  color: $text-tertiary;
}

.loading-more {
  display: flex;
  justify-content: center;
  padding: $space-lg 0;
}
</style>