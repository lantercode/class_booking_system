<template>
  <div class="membership-container">
    <header class="page-header">
      <el-button text @click="$router.push('/profile')">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
      <span class="header-title">我的会员卡</span>
      <div style="width: 60px"></div>
    </header>

    <div class="tab-bar">
      <div
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-item"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
        <span v-if="tab.count() > 0" class="tab-count">{{ tab.count() }}</span>
      </div>
    </div>

    <div class="membership-list">
      <div v-if="loading" v-loading="true" class="loading-wrapper">
        <div style="height: 80px"></div>
      </div>

      <div v-else-if="loadError" class="error-wrapper">
        <el-result icon="error" title="加载会员卡失败" :sub-title="loadError">
          <template #extra>
            <el-button type="primary" @click="fetchCards">重试</el-button>
          </template>
        </el-result>
      </div>

      <div v-else-if="filteredCards.length === 0" class="empty-wrapper">
        <el-empty description="暂无会员卡" />
      </div>

      <template v-else>
        <div
          v-for="card in filteredCards"
          :key="card.id"
          class="card-item"
          @click="goDetail(card.id)"
        >
          <div class="card-main">
            <div class="card-header">
              <span class="card-name">{{ card.product_name || '会员卡' }}</span>
              <el-tag :type="statusTagType(card.status)" size="small">
                {{ statusText(card.status) }}
              </el-tag>
            </div>
            <div class="card-meta">
              <span>卡号：{{ card.card_no || '-' }}</span>
              <span>{{ cardTypeText(card.card_type) }}</span>
            </div>
            <div class="card-footer">
              <span v-if="card.card_type === 'count'" class="card-credits">
                剩余 {{ card.remaining_credits ?? 0 }} / {{ card.total_credits ?? 0 }} 次
              </span>
              <span v-else class="card-credits">{{ cardTypeText(card.card_type) }}</span>
              <span class="card-expire">
                有效期至 {{ formatDate(card.expire_at) }}
              </span>
            </div>
          </div>
          <el-icon class="card-arrow"><ArrowRight /></el-icon>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { membershipCardApi, type MembershipCard } from '@dance-saas/api-client'

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

const cards = ref<MembershipCard[]>([])
const loading = ref(false)
const loadError = ref('')
const activeTab = ref('all')

const tabs = computed(() => [
  { key: 'all', label: '全部', count: () => cards.value.length },
  {
    key: 'valid',
    label: '可用',
    count: () => cards.value.filter((c) => isUsableStatus(c.status)).length,
  },
  {
    key: 'invalid',
    label: '不可用',
    count: () => cards.value.filter((c) => !isUsableStatus(c.status)).length,
  },
])

const filteredCards = computed(() => {
  if (activeTab.value === 'valid') {
    return cards.value.filter((c) => isUsableStatus(c.status))
  }
  if (activeTab.value === 'invalid') {
    return cards.value.filter((c) => !isUsableStatus(c.status))
  }
  return cards.value
})

function isUsableStatus(status: number): boolean {
  return status === 0 || status === 1 || status === 3
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

function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  return String(value).slice(0, 10)
}

async function fetchCards() {
  loading.value = true
  loadError.value = ''
  try {
    // 不传 student_id：后端已强制非 admin 仅返回本人会员卡
    const res = await membershipCardApi.list({ page: 1, page_size: 100 })
    cards.value = res.data.items || []
  } catch (e: any) {
    loadError.value =
      e?.response?.data?.msg || e?.message || '加载会员卡列表失败'
    ElMessage.error(loadError.value)
    cards.value = []
  } finally {
    loading.value = false
  }
}

function goDetail(id: number) {
  router.push(`/membership/${id}`)
}

onMounted(() => {
  fetchCards()
})
</script>

<style scoped lang="scss">
.membership-container {
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

.tab-bar {
  display: flex;
  background: #fff;
  margin: 16px 16px 0;
  border-radius: 12px;
  padding: 4px;
  gap: 4px;

  .tab-item {
    flex: 1;
    text-align: center;
    padding: 8px 0;
    font-size: 14px;
    color: #606266;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;

    &.active {
      background: #409eff;
      color: #fff;
      font-weight: 500;
    }

    .tab-count {
      margin-left: 4px;
      font-size: 12px;
    }
  }
}

.membership-list {
  padding: 16px;
}

.loading-wrapper,
.error-wrapper,
.empty-wrapper {
  padding: 60px 0;
  background: #fff;
  border-radius: 12px;
}

.card-item {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  cursor: pointer;
  transition: transform 0.2s;

  &:active {
    transform: scale(0.99);
  }

  .card-main {
    flex: 1;
    min-width: 0;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;

    .card-name {
      font-size: 15px;
      font-weight: 600;
      color: #303133;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .card-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    font-size: 13px;
    color: #909399;
    margin-bottom: 6px;
  }

  .card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;

    .card-credits {
      font-size: 13px;
      color: #409eff;
      font-weight: 500;
    }

    .card-expire {
      font-size: 12px;
      color: #c0c4cc;
    }
  }

  .card-arrow {
    color: #c0c4cc;
    flex-shrink: 0;
  }
}
</style>
