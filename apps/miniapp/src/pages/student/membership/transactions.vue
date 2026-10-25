<template>
  <view class="membership-tx-page">
    <!-- 加载中（首屏） -->
    <view v-if="loading && transactions.length === 0" class="state-block">
      <text class="state-text">加载中...</text>
    </view>

    <!-- 错误（含 403 / 404 分支） -->
    <view v-else-if="errorMessage && transactions.length === 0" class="state-block">
      <AppIcon name="card-invalid" :size="96" color="#b8a088" />
      <text class="state-title">{{ errorMessage }}</text>
      <view class="state-btn" @tap="goBackList">
        <text>返回列表</text>
      </view>
    </view>

    <!-- 空状态 -->
    <view v-else-if="transactions.length === 0" class="state-block">
      <AppIcon name="clock" :size="96" color="#b8a088" />
      <text class="state-title">暂无使用记录</text>
    </view>

    <!-- 流水列表 -->
    <template v-else>
      <view class="tx-list">
        <view
          v-for="tx in transactions"
          :key="tx.id"
          class="tx-item"
        >
          <view class="tx-header">
            <text class="tx-type">{{ getTypeText(tx.operation_type) }}</text>
            <text class="tx-amount" :class="getAmountClass(tx.change_amount)">
              {{ formatAmount(tx.change_amount) }}
            </text>
          </view>

          <view class="tx-meta">
            <text class="tx-time">{{ formatDateTimeText(tx.created_at) }}</text>
            <text class="tx-balance">余额 {{ tx.balance_after }}</text>
          </view>

          <view v-if="tx.remark" class="tx-remark">
            <text class="tx-remark-text">{{ tx.remark }}</text>
          </view>

          <view v-if="tx.booking_id" class="tx-booking">
            <AppIcon name="calendar-check" :size="24" color="#c9a66b" />
            <text class="tx-booking-text">关联预约 #{{ tx.booking_id }}</text>
          </view>
        </view>
      </view>

      <!-- 分页状态 -->
      <view class="list-footer">
        <text v-if="loadingMore" class="footer-text">加载中...</text>
        <text v-else-if="hasMore" class="footer-text">上拉加载更多</text>
        <text v-else class="footer-text">没有更多了</text>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { membershipApi } from "@/api";
import AppIcon from "@/components/AppIcon.vue";
import { checkLogin } from "@/utils/auth";
import { onLoad, onReachBottom } from "@dcloudio/uni-app";
import { computed, ref } from "vue";

/** 消费流水（字段对齐后端 MembershipCardTransactionResponse；不展示 operator_id / idempotency_key / public_id） */
interface MembershipTransaction {
  id: number;
  card_id: number;
  booking_id?: number | null;
  operation_type: string;
  change_amount: number;
  balance_after: number;
  remark?: string | null;
  created_at: string;
}

const PAGE_SIZE = 20;

/** 枚举实际值见 apps/api/src/app/modules/membership/models.py TransactionType */
const TYPE_TEXT: Record<string, string> = {
  issue: "发放",
  consume: "扣次",
  restore: "回补",
  recharge: "充值",
  refund: "退款",
  adjust: "调整",
  expire: "过期清零",
};

const cardId = ref(0);
const transactions = ref<MembershipTransaction[]>([]);
const page = ref(1);
const total = ref(0);
const loading = ref(true);
const loadingMore = ref(false);
const errorMessage = ref("");

const hasMore = computed(() => transactions.value.length < total.value);

function getTypeText(type: string): string {
  return TYPE_TEXT[type] || "其他";
}

function getAmountClass(amount: number): string {
  if (amount > 0) return "amount-positive";
  if (amount < 0) return "amount-negative";
  return "amount-zero";
}

function formatAmount(amount: number): string {
  if (amount > 0) return `+${amount}`;
  return String(amount);
}

/** 后端 created_at 为 ISO 时间字符串，展示为 YYYY-MM-DD HH:mm */
function formatDateTimeText(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const pad = (num: number) => String(num).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(
    date.getDate(),
  )} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** 错误文案：403 / 404 使用产品约定文案，其余展示后端 msg */
function resolveErrorMessage(error: any): string {
  const statusCode = Number(error?.statusCode);
  if (statusCode === 403) return "无权查看该会员卡";
  if (statusCode === 404) return "会员卡不存在或已失效";
  return error?.message || "加载使用记录失败";
}

async function fetchTransactions(reset = false) {
  try {
    if (reset) {
      loading.value = true;
      errorMessage.value = "";
    } else {
      loadingMore.value = true;
    }

    const res = await membershipApi.getTransactions({
      card_id: cardId.value,
      page: page.value,
      page_size: PAGE_SIZE,
    });

    const data = (res?.data || {}) as {
      items?: MembershipTransaction[];
      total?: number;
    };
    const items = Array.isArray(data.items) ? data.items : [];

    transactions.value = reset
      ? items
      : transactions.value.concat(items);
    total.value = typeof data.total === "number" ? data.total : items.length;
  } catch (error: any) {
    console.error("加载使用记录失败:", error);
    if (reset) {
      transactions.value = [];
      total.value = 0;
      errorMessage.value = resolveErrorMessage(error);
    } else {
      uni.showToast({ title: resolveErrorMessage(error), icon: "none" });
      // 回退页码，避免下一轮重复跳页
      page.value = Math.max(1, page.value - 1);
    }
  } finally {
    loading.value = false;
    loadingMore.value = false;
  }
}

function goBackList() {
  uni.redirectTo({ url: "/pages/student/membership/index" });
}

onLoad((options) => {
  if (!checkLogin("student")) return;

  const id = Number(options?.card_id);
  if (!id || Number.isNaN(id)) {
    loading.value = false;
    errorMessage.value = "会员卡不存在或已失效";
    return;
  }

  cardId.value = id;
  fetchTransactions(true);
});

onReachBottom(() => {
  if (loading.value || loadingMore.value) return;
  if (!hasMore.value) return;
  page.value += 1;
  fetchTransactions(false);
});
</script>

<style lang="scss">
.membership-tx-page {
  // 不使用 page-container：其 overflow:hidden + 100vh 会阻止页面原生滚动，
  // 而 onReachBottom 续页依赖页面滚动（pages.json 已置 disableScroll:false）
  width: 100%;
  min-height: 100vh;
  background: linear-gradient(180deg, #faf6f0 0%, #f5ede3 100%);
  padding: $space-md;
  padding-bottom: 40rpx;
  box-sizing: border-box;
}

// ===== 状态块 =====
.state-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 160rpx $space-md;
  gap: $space-sm;

  .state-text {
    font-size: $font-size-body;
    color: $text-tertiary;
  }

  .state-title {
    font-size: $font-size-body;
    color: $text-secondary;
    text-align: center;
  }

  .state-btn {
    margin-top: $space-sm;
    padding: 16rpx 48rpx;
    background: linear-gradient(135deg, #d4b896 0%, #c9a66b 100%);
    border-radius: $radius-full;
    box-shadow: $shadow-button;

    text {
      font-size: $font-size-body;
      color: #fff;
      font-weight: $font-weight-medium;
    }
  }
}

// ===== 流水列表 =====
.tx-list {
  display: flex;
  flex-direction: column;
  gap: $space-sm;
}

.tx-item {
  padding: $space-md;
  background: rgba(255, 255, 255, 0.92);
  border-radius: $radius-lg;
  border: 1rpx solid rgba(201, 166, 107, 0.12);
  box-shadow: $shadow-xs;
}

.tx-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: $space-xs;

  .tx-type {
    font-size: $font-size-body;
    font-weight: $font-weight-bold;
    color: #333;
  }

  .tx-amount {
    font-size: $font-size-h3;
    font-weight: $font-weight-bold;
    font-family: "DIN Alternate", "Helvetica Neue", sans-serif;

    &.amount-positive {
      color: #7cb986;
    }

    &.amount-negative {
      color: #d4847a;
    }

    &.amount-zero {
      color: $text-tertiary;
    }
  }
}

.tx-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12rpx;

  .tx-time {
    font-size: $font-size-caption;
    color: $text-tertiary;
  }

  .tx-balance {
    font-size: $font-size-caption;
    color: $text-secondary;
  }
}

.tx-remark {
  margin-top: 12rpx;
  padding: 10rpx 16rpx;
  background: rgba(201, 166, 107, 0.06);
  border-radius: $radius-sm;

  .tx-remark-text {
    font-size: $font-size-caption;
    color: $text-secondary;
    word-break: break-all;
  }
}

.tx-booking {
  display: flex;
  align-items: center;
  gap: 8rpx;
  margin-top: 12rpx;

  .tx-booking-text {
    font-size: $font-size-caption;
    color: #c9a66b;
  }
}

.list-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: $space-md 0;

  .footer-text {
    font-size: $font-size-caption;
    color: $text-disabled;
  }
}
</style>
