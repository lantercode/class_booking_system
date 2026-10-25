<template>
  <div class="membership-detail-container">
    <header class="page-header">
      <el-button text @click="$router.push('/membership')">
        <el-icon><ArrowLeft /></el-icon>
        返回列表
      </el-button>
      <span class="header-title">会员卡详情</span>
      <div style="width: 80px"></div>
    </header>

    <div class="detail-body">
      <div v-if="loading" v-loading="true" class="loading-wrapper">
        <div style="height: 120px"></div>
      </div>

      <div v-else-if="loadError" class="error-wrapper">
        <el-result icon="warning" title="无法查看会员卡" :sub-title="loadError">
          <template #extra>
            <el-button @click="$router.push('/membership')">返回列表</el-button>
            <el-button type="primary" @click="fetchCard">重试</el-button>
          </template>
        </el-result>
      </div>

      <template v-else-if="card">
        <div class="hero-card">
          <div class="hero-header">
            <span class="hero-name">{{ card.product_name || '会员卡' }}</span>
            <el-tag :type="statusTagType(card.status)" size="small">
              {{ statusText(card.status) }}
            </el-tag>
          </div>
          <div class="hero-card-no">{{ card.card_no || '-' }}</div>
          <div class="hero-type">{{ cardTypeText(card.card_type) }}</div>
        </div>

        <div class="info-card">
          <div class="section-title">有效期</div>
          <div class="info-row">
            <span class="info-label">生效时间</span>
            <span class="info-value">{{ formatDateTime(card.valid_from) }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">到期时间</span>
            <span class="info-value">{{ formatDateTime(card.expire_at) }}</span>
          </div>
        </div>

        <div v-if="card.card_type === 'count'" class="info-card">
          <div class="section-title">课时</div>
          <div class="credits-row">
            <div class="credits-item">
              <span class="credits-value">{{ card.total_credits ?? 0 }}</span>
              <span class="credits-label">总次数</span>
            </div>
            <div class="credits-item">
              <span class="credits-value">{{ card.used_credits ?? 0 }}</span>
              <span class="credits-label">已使用</span>
            </div>
            <div class="credits-item">
              <span class="credits-value remaining">{{ card.remaining_credits ?? 0 }}</span>
              <span class="credits-label">剩余</span>
            </div>
          </div>
        </div>

        <div v-if="card.status === 3" class="info-card">
          <div class="section-title">冻结信息</div>
          <div class="info-row">
            <span class="info-label">冻结时间</span>
            <span class="info-value">{{ formatDateTime(card.frozen_at) }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">预计解冻</span>
            <span class="info-value">{{ formatDateTime(card.frozen_until) }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">冻结原因</span>
            <span class="info-value">{{ card.frozen_reason || '—' }}</span>
          </div>
        </div>

        <div v-if="card.status === 6" class="info-card">
          <div class="section-title">作废信息</div>
          <div class="info-row">
            <span class="info-label">作废时间</span>
            <span class="info-value">{{ formatDateTime(card.cancelled_at) }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">作废原因</span>
            <span class="info-value">{{ card.cancelled_reason || '—' }}</span>
          </div>
        </div>

        <div class="action-bar">
          <el-button @click="goTransactions">查看使用记录</el-button>
          <el-button type="primary" @click="$router.push('/courses')">去预约</el-button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { membershipCardApi, type MembershipCard } from '@dance-saas/api-client'

/** 详情接口额外返回作废信息（后端 MembershipCardResponse），api-client 卡片类型暂未声明 */
type MembershipCardDetail = MembershipCard & {
  cancelled_at?: string | null
  cancelled_reason?: string | null
}

const route = useRoute()
const router = useRouter()

const STATUS_TEXT: Record<number, string> = {
  0: '未激活',
  1: '使用中',
  2: '已过期',
  3: '冻结中',
  6: '已作废',
}

const CARD_TYPE_TEXT: Record<string, string> = {
  count: '次卡',
  period: '期卡',
  unlimited: '无限卡',
}

const card = ref<MembershipCardDetail | null>(null)
const loading = ref(false)
const loadError = ref('')

function getCardId(): number {
  const id = Number(route.params.id)
  return Number.isNaN(id) ? 0 : id
}

function statusText(status: number): string {
  return STATUS_TEXT[status] || '未知状态'
}

function statusTagType(status: number) {
  const map: Record<number, string> = {
    0: 'warning',
    1: 'success',
    2: 'danger',
    3: 'info',
    6: 'info',
  }
  return map[status] || 'info'
}

function cardTypeText(cardType: string | undefined): string {
  if (!cardType) return '会员卡'
  return CARD_TYPE_TEXT[cardType] || cardType
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  return String(value).replace('T', ' ').slice(0, 19)
}

async function fetchCard() {
  const id = getCardId()
  if (!id) {
    loadError.value = '会员卡不存在或已失效'
    return
  }

  loading.value = true
  loadError.value = ''
  try {
    const res = await membershipCardApi.get(id)
    card.value = (res.data || null) as MembershipCardDetail | null
    if (!card.value) {
      loadError.value = '会员卡不存在或已失效'
    }
  } catch (e: any) {
    const status = e?.response?.status
    if (status === 403) {
      loadError.value = '无权查看该会员卡'
    } else if (status === 404) {
      loadError.value = '会员卡不存在或已失效'
    } else {
      loadError.value = e?.response?.data?.msg || e?.message || '加载会员卡详情失败'
    }
    card.value = null
  } finally {
    loading.value = false
  }
}

function goTransactions() {
  if (!card.value) return
  router.push(`/membership/${card.value.id}/transactions`)
}

onMounted(() => {
  fetchCard()
})
</script>

<style scoped lang="scss">
.membership-detail-container {
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

.detail-body {
  padding: 16px;
}

.loading-wrapper,
.error-wrapper {
  padding: 60px 0;
  background: #fff;
  border-radius: 12px;
}

.hero-card {
  background: linear-gradient(135deg, #ecf5ff 0%, #f5f7fa 100%);
  border: 1px solid #d9ecff;
  border-radius: 12px;
  padding: 20px 16px;
  margin-bottom: 16px;

  .hero-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;

    .hero-name {
      font-size: 18px;
      font-weight: 600;
      color: #303133;
    }
  }

  .hero-card-no {
    margin-top: 12px;
    font-size: 13px;
    color: #909399;
    letter-spacing: 0.5px;
  }

  .hero-type {
    margin-top: 6px;
    font-size: 13px;
    color: #409eff;
  }
}

.info-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);

  .section-title {
    font-size: 14px;
    font-weight: 600;
    color: #303133;
    padding-bottom: 12px;
    border-bottom: 1px solid #f0f2f5;
    margin-bottom: 4px;
  }
}

.info-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 0;

  .info-label {
    font-size: 13px;
    color: #909399;
    flex-shrink: 0;
  }

  .info-value {
    font-size: 13px;
    color: #303133;
    text-align: right;
    word-break: break-all;
  }
}

.credits-row {
  display: flex;
  align-items: center;
  justify-content: space-around;
  padding-top: 12px;
}

.credits-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;

  .credits-value {
    font-size: 22px;
    font-weight: 700;
    color: #303133;

    &.remaining {
      color: #409eff;
    }
  }

  .credits-label {
    font-size: 12px;
    color: #909399;
  }
}

.action-bar {
  display: flex;
  gap: 12px;

  .el-button {
    flex: 1;
  }
}
</style>
