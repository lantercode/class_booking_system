<template>
  <div class="membership-tx-container">
    <header class="page-header">
      <el-button text @click="$router.push(`/membership/${cardId}`)">
        <el-icon><ArrowLeft /></el-icon>
        返回详情
      </el-button>
      <span class="header-title">使用记录</span>
      <div style="width: 80px"></div>
    </header>

    <div class="tx-body">
      <div v-if="loading && transactions.length === 0" v-loading="true" class="loading-wrapper">
        <div style="height: 80px"></div>
      </div>

      <div v-else-if="loadError && transactions.length === 0" class="error-wrapper">
        <el-result icon="warning" title="无法查看使用记录" :sub-title="loadError">
          <template #extra>
            <el-button @click="$router.push('/membership')">返回列表</el-button>
            <el-button type="primary" @click="fetchTransactions(true)">重试</el-button>
          </template>
        </el-result>
      </div>

      <div v-else-if="transactions.length === 0" class="empty-wrapper">
        <el-empty description="暂无使用记录" />
      </div>

      <template v-else>
        <div class="tx-list">
          <div v-for="tx in transactions" :key="tx.id" class="tx-item">
            <div class="tx-header">
              <span class="tx-type">{{ typeText(tx.operation_type) }}</span>
              <span class="tx-amount" :class="amountClass(tx.change_amount)">
                {{ formatAmount(tx.change_amount) }}
              </span>
            </div>
            <div class="tx-meta">
              <span class="tx-time">{{ formatDateTime(tx.created_at) }}</span>
              <span class="tx-balance">余额 {{ tx.balance_after }}</span>
            </div>
            <div v-if="tx.remark" class="tx-remark">{{ tx.remark }}</div>
            <div v-if="tx.booking_id" class="tx-booking">关联预约 #{{ tx.booking_id }}</div>
          </div>
        </div>

        <div class="list-footer">
          <el-button
            v-if="hasMore"
            :loading="loadingMore"
            size="small"
            @click="loadMore"
          >
            加载更多
          </el-button>
          <span v-else class="footer-text">没有更多了</span>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import {
  membershipCardApi,
  type MembershipCardTransaction,
} from '@dance-saas/api-client'

const route = useRoute()

const PAGE_SIZE = 20

/** 枚举实际值见 apps/api/src/app/modules/membership/models.py TransactionType */
const TYPE_TEXT: Record<string, string> = {
  issue: '发放',
  consume: '扣次',
  restore: '回补',
  recharge: '充值',
  refund: '退款',
  adjust: '调整',
  expire: '过期清零',
}

const cardId = computed(() => {
  const id = Number(route.params.id)
  return Number.isNaN(id) ? 0 : id
})

const transactions = ref<MembershipCardTransaction[]>([])
const page = ref(1)
const total = ref(0)
const loading = ref(false)
const loadingMore = ref(false)
const loadError = ref('')

const hasMore = computed(() => transactions.value.length < total.value)

function typeText(type: string): string {
  return TYPE_TEXT[type] || '其他'
}

function amountClass(amount: number) {
  if (amount > 0) return 'amount-positive'
  if (amount < 0) return 'amount-negative'
  return 'amount-zero'
}

function formatAmount(amount: number): string {
  return amount > 0 ? `+${amount}` : String(amount)
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  return String(value).replace('T', ' ').slice(0, 16)
}

function resolveErrorMessage(error: any): string {
  const status = error?.response?.status
  if (status === 403) return '无权查看该会员卡'
  if (status === 404) return '会员卡不存在或已失效'
  return error?.response?.data?.msg || error?.message || '加载使用记录失败'
}

async function fetchTransactions(reset = false) {
  if (!cardId.value) {
    loadError.value = '会员卡不存在或已失效'
    return
  }

  if (reset) {
    loading.value = true
    loadError.value = ''
    page.value = 1
  } else {
    loadingMore.value = true
  }

  try {
    const res = await membershipCardApi.getTransactions({
      card_id: cardId.value,
      page: page.value,
      page_size: PAGE_SIZE,
    })
    const items = res.data.items || []
    transactions.value = reset ? items : transactions.value.concat(items)
    total.value = typeof res.data.total === 'number' ? res.data.total : items.length
  } catch (e: any) {
    if (reset) {
      transactions.value = []
      total.value = 0
      loadError.value = resolveErrorMessage(e)
    } else {
      // 回退页码，避免重复跳过一页
      page.value = Math.max(1, page.value - 1)
    }
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function loadMore() {
  if (loading.value || loadingMore.value || !hasMore.value) return
  page.value += 1
  fetchTransactions(false)
}

onMounted(() => {
  fetchTransactions(true)
})
</script>

<style scoped lang="scss">
.membership-tx-container {
  min-height: 100vh;
  background: #f5f7fa;
  max-width: 800px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);

  .header-title {
    font-size: 16px;
    font-weight: 600;
    color: #303133;
  }
}

.tx-body {
  padding: 16px;
}

.loading-wrapper,
.error-wrapper,
.empty-wrapper {
  padding: 60px 0;
  background: #fff;
  border-radius: 12px;
}

.tx-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tx-item {
  background: #fff;
  border-radius: 12px;
  padding: 14px 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);

  .tx-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;

    .tx-type {
      font-size: 15px;
      font-weight: 600;
      color: #303133;
    }

    .tx-amount {
      font-size: 18px;
      font-weight: 700;

      &.amount-positive {
        color: #67c23a;
      }

      &.amount-negative {
        color: #f56c6c;
      }

      &.amount-zero {
        color: #909399;
      }
    }
  }

  .tx-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    margin-top: 8px;

    .tx-time {
      font-size: 12px;
      color: #c0c4cc;
    }

    .tx-balance {
      font-size: 12px;
      color: #909399;
    }
  }

  .tx-remark {
    margin-top: 8px;
    padding: 6px 10px;
    background: #f5f7fa;
    border-radius: 6px;
    font-size: 12px;
    color: #606266;
    word-break: break-all;
  }

  .tx-booking {
    margin-top: 8px;
    font-size: 12px;
    color: #409eff;
  }
}

.list-footer {
  display: flex;
  justify-content: center;
  padding: 16px 0;

  .footer-text {
    font-size: 12px;
    color: #c0c4cc;
  }
}
</style>
