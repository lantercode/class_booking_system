<template>
  <view class="membership-detail-page">
    <!-- 加载中 -->
    <view v-if="loading" class="state-block">
      <text class="state-text">加载中...</text>
    </view>

    <!-- 错误（含 403 / 404 分支） -->
    <view v-else-if="errorMessage" class="state-block">
      <AppIcon name="card-invalid" :size="96" color="#b8a088" />
      <text class="state-title">{{ errorMessage }}</text>
      <view class="state-btn" @tap="goBackList">返回列表</view>
    </view>

    <!-- 详情 -->
    <template v-else-if="card">
      <!-- 卡面 -->
      <view class="card-hero">
        <view class="hero-header">
          <text class="hero-name">{{ displayProductName }}</text>
          <view class="card-status-badge" :class="statusClass">
            <view class="badge-dot"></view>
            <text class="badge-text">{{ statusText }}</text>
          </view>
        </view>

        <text class="hero-card-no">{{ displayCardNo }}</text>

        <view class="hero-type">
          <AppIcon
            name="membership-card"
            :size="28"
            color="rgba(90, 74, 42, 0.6)"
          />
          <text class="hero-type-text">{{ cardTypeText }}</text>
        </view>
      </view>

      <!-- 有效期 -->
      <view class="info-card">
        <view class="section-head">
          <text class="section-title">有效期</text>
          <view class="section-line"></view>
        </view>
        <view class="info-row">
          <text class="info-label">生效时间</text>
          <text class="info-value">{{ card.valid_from || "—" }}</text>
        </view>
        <view class="info-row">
          <text class="info-label">到期时间</text>
          <text class="info-value">{{ card.expire_at || "—" }}</text>
        </view>
      </view>

      <!-- 次卡课时 -->
      <view v-if="card.card_type === 'count'" class="info-card">
        <view class="section-head">
          <text class="section-title">课时</text>
          <view class="section-line"></view>
        </view>
        <view class="credits-row">
          <view class="credits-item">
            <text class="credits-value">{{ card.total_credits ?? 0 }}</text>
            <text class="credits-label">总次数</text>
          </view>
          <view class="credits-divider"></view>
          <view class="credits-item">
            <text class="credits-value">{{ card.used_credits ?? 0 }}</text>
            <text class="credits-label">已使用</text>
          </view>
          <view class="credits-divider"></view>
          <view class="credits-item">
            <text class="credits-value credits-remaining">{{
              card.remaining_credits ?? 0
            }}</text>
            <text class="credits-label">剩余</text>
          </view>
        </view>
      </view>

      <!-- 冻结信息 -->
      <view v-if="card.status === 3" class="info-card">
        <view class="section-head">
          <text class="section-title">冻结信息</text>
          <view class="section-line"></view>
        </view>
        <view class="info-row">
          <text class="info-label">冻结时间</text>
          <text class="info-value">{{ card.frozen_at || "—" }}</text>
        </view>
        <view class="info-row">
          <text class="info-label">预计解冻</text>
          <text class="info-value">{{ card.frozen_until || "未设置" }}</text>
        </view>
        <view class="info-row">
          <text class="info-label">冻结原因</text>
          <text class="info-value">{{ card.frozen_reason || "—" }}</text>
        </view>
      </view>

      <!-- 作废信息 -->
      <view v-if="card.status === 6" class="info-card">
        <view class="section-head">
          <text class="section-title">作废信息</text>
          <view class="section-line"></view>
        </view>
        <view class="info-row">
          <text class="info-label">作废时间</text>
          <text class="info-value">{{ card.cancelled_at || "—" }}</text>
        </view>
        <view class="info-row">
          <text class="info-label">作废原因</text>
          <text class="info-value">{{ card.cancelled_reason || "—" }}</text>
        </view>
      </view>

      <!-- 入口操作 -->
      <view class="action-bar">
        <view class="action-btn secondary" @tap="goTransactions">
          <text class="action-text secondary-text">查看使用记录</text>
        </view>
        <view class="action-btn primary" @tap="goSchedule">
          <text class="action-text primary-text">去预约</text>
        </view>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { membershipApi } from "@/api";
import AppIcon from "@/components/AppIcon.vue";
import { checkLogin } from "@/utils/auth";
import { onLoad } from "@dcloudio/uni-app";
import { computed, ref } from "vue";

/** 会员卡详情（字段对齐后端 MembershipCardResponse） */
interface MembershipCardDetail {
  id: number;
  card_no?: string | null;
  card_type?: string;
  product_name?: string | null;
  total_credits?: number | null;
  used_credits?: number;
  remaining_credits?: number | null;
  status: number;
  valid_from?: string | null;
  expire_at?: string | null;
  frozen_at?: string | null;
  frozen_until?: string | null;
  frozen_reason?: string | null;
  cancelled_at?: string | null;
  cancelled_reason?: string | null;
}

const cardId = ref(0);
const fallbackCardNo = ref("");
const fallbackProductName = ref("");
const card = ref<MembershipCardDetail | null>(null);
const loading = ref(true);
const errorMessage = ref("");

const STATUS_TEXT: Record<number, string> = {
  0: "未激活",
  1: "使用中",
  2: "已过期",
  3: "冻结中",
  6: "已作废",
};

const STATUS_CLASS: Record<number, string> = {
  0: "status-pending",
  1: "status-active",
  2: "status-expired",
  3: "status-frozen",
  6: "status-voided",
};

const CARD_TYPE_TEXT: Record<string, string> = {
  count: "次卡",
  period: "期卡",
  unlimited: "无限卡",
};

const statusText = computed(() =>
  card.value ? STATUS_TEXT[card.value.status] || "未知状态" : "",
);

const statusClass = computed(() =>
  card.value ? STATUS_CLASS[card.value.status] || "status-used-up" : "",
);

const cardTypeText = computed(() => {
  if (!card.value?.card_type) return "会员卡";
  return CARD_TYPE_TEXT[card.value.card_type] || card.value.card_type;
});

const displayProductName = computed(
  () => card.value?.product_name || fallbackProductName.value || "会员卡",
);

const displayCardNo = computed(
  () => card.value?.card_no || fallbackCardNo.value || "-",
);

/** 解析 query 参数（uni-app 可能已自动解码，重复解码时兜底原文） */
function safeDecode(value?: string): string {
  if (!value) return "";
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

/** 错误文案：403 / 404 使用产品约定文案，其余展示后端 msg */
function resolveErrorMessage(error: any): string {
  const statusCode = Number(error?.statusCode);
  if (statusCode === 403) return "无权查看该会员卡";
  if (statusCode === 404) return "会员卡不存在或已失效";
  return error?.message || "加载会员卡详情失败";
}

async function loadDetail() {
  try {
    loading.value = true;
    errorMessage.value = "";
    const res = await membershipApi.getCardDetail(cardId.value);
    card.value = (res?.data || null) as MembershipCardDetail | null;
    if (!card.value) {
      errorMessage.value = "会员卡不存在或已失效";
    }
  } catch (error: any) {
    console.error("加载会员卡详情失败:", error);
    card.value = null;
    errorMessage.value = resolveErrorMessage(error);
  } finally {
    loading.value = false;
  }
}

function goBackList() {
  if (getCurrentPages().length > 1) {
    uni.navigateBack();
  } else {
    uni.redirectTo({ url: "/pages/student/membership/index" });
  }
}

function goTransactions() {
  if (!card.value) return;
  uni.navigateTo({
    url: `/pages/student/membership/transactions?card_id=${card.value.id}`,
  });
}

function goSchedule() {
  uni.redirectTo({ url: "/pages/student/schedule/index" });
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
  fallbackCardNo.value = safeDecode(options?.card_no);
  fallbackProductName.value = safeDecode(options?.product_name);
  loadDetail();
});
</script>

<style lang="scss">
.membership-detail-page {
  // 不使用 page-container：其 overflow:hidden + 100vh 会阻止页面原生滚动
  width: 100%;
  min-height: 100vh;
  background: linear-gradient(180deg, #faf6f0 0%, #f5ede3 100%);
  padding: $space-md;
  padding-bottom: 60rpx;
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

// ===== 卡面 =====
.card-hero {
  position: relative;
  padding: $space-lg;
  border-radius: $radius-lg;
  background: linear-gradient(
    135deg,
    #fdf6e9 0%,
    #f9edda 30%,
    #f5e6c8 60%,
    #f0d9a8 100%
  );
  border: 1rpx solid $primary-border;
  box-shadow: 0 4rpx 20rpx rgba(201, 166, 107, 0.2);
}

.hero-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: $space-xs;

  .hero-name {
    flex: 1;
    font-size: $font-size-h3;
    font-weight: $font-weight-bold;
    color: #333;
  }
}

.hero-card-no {
  display: block;
  margin-top: $space-sm;
  font-size: $font-size-body_sm;
  color: rgba(90, 74, 42, 0.6);
  letter-spacing: $letter-spacing-wide;
}

.hero-type {
  display: flex;
  align-items: center;
  gap: 8rpx;
  margin-top: $space-sm;

  .hero-type-text {
    font-size: $font-size-caption;
    color: rgba(90, 74, 42, 0.6);
  }
}

// ===== 状态徽标（复用列表页视觉口径） =====
.card-status-badge {
  display: flex;
  align-items: center;
  gap: 4rpx;
  padding: 4rpx 12rpx;
  border-radius: 20rpx;
  font-size: $font-size-caption;
  min-width: 100rpx;
  justify-content: center;

  .badge-dot {
    width: 8rpx;
    height: 8rpx;
    border-radius: 50%;
  }

  .badge-text {
    font-weight: $font-weight-medium;
  }

  &.status-active {
    background: rgba(76, 175, 80, 0.12);

    .badge-dot {
      background: #4caf50;
    }

    .badge-text {
      color: #2e7d32;
    }
  }

  &.status-used-up {
    background: rgba(158, 158, 158, 0.1);

    .badge-dot {
      background: #9e9e9e;
    }

    .badge-text {
      color: #757575;
    }
  }

  &.status-pending {
    background: rgba(255, 183, 77, 0.15);

    .badge-dot {
      background: #ffb74d;
    }

    .badge-text {
      color: #e65100;
    }
  }

  &.status-expired {
    background: rgba(244, 67, 54, 0.1);

    .badge-dot {
      background: #ef5350;
    }

    .badge-text {
      color: #c62828;
    }
  }

  &.status-voided {
    background: rgba(158, 158, 158, 0.1);

    .badge-dot {
      background: #bdbdbd;
    }

    .badge-text {
      color: #757575;
    }
  }

  &.status-frozen {
    background: rgba(100, 149, 237, 0.12);

    .badge-dot {
      background: #6495ed;
    }

    .badge-text {
      color: #4a7bd4;
    }
  }
}

// ===== 信息卡片 =====
.info-card {
  margin-top: $space-md;
  padding: $space-md;
  background: rgba(255, 255, 255, 0.9);
  border-radius: $radius-lg;
  border: 1rpx solid rgba(201, 166, 107, 0.12);
  box-shadow: $shadow-xs;
}

.section-head {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: $space-sm;

  .section-title {
    font-size: $font-size-body;
    font-weight: $font-weight-bold;
    color: #333;
  }

  .section-line {
    flex: 1;
    height: 1rpx;
    background: linear-gradient(90deg, rgba(201, 166, 107, 0.3), transparent);
  }
}

.info-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: $space-md;
  padding: 12rpx 0;

  .info-label {
    font-size: $font-size-body_sm;
    color: $text-tertiary;
    flex-shrink: 0;
  }

  .info-value {
    font-size: $font-size-body_sm;
    color: $text-primary;
    text-align: right;
    word-break: break-all;
  }
}

// ===== 课时 =====
.credits-row {
  display: flex;
  align-items: center;
  justify-content: space-around;
  padding-top: 8rpx;
}

.credits-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8rpx;

  .credits-value {
    font-size: 48rpx;
    font-weight: $font-weight-bold;
    color: #333;
    font-family: "DIN Alternate", "Helvetica Neue", sans-serif;
    line-height: 1;

    &.credits-remaining {
      color: #c9a66b;
    }
  }

  .credits-label {
    font-size: $font-size-caption;
    color: $text-tertiary;
  }
}

.credits-divider {
  width: 1rpx;
  height: 48rpx;
  background: $divider-color;
}

// ===== 操作入口 =====
.action-bar {
  display: flex;
  gap: $space-sm;
  margin-top: $space-lg;
}

.action-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24rpx 0;
  border-radius: $radius-full;
  transition: all 0.2s ease;

  &:active {
    transform: scale(0.97);
    opacity: 0.9;
  }

  &.primary {
    background: linear-gradient(135deg, #d4b896 0%, #c9a66b 100%);
    box-shadow: $shadow-button;
  }

  &.secondary {
    background: rgba(255, 255, 255, 0.9);
    border: 1rpx solid $primary-border;
  }

  .action-text {
    font-size: $font-size-body;
    font-weight: $font-weight-medium;
  }

  .primary-text {
    color: #fff;
  }

  .secondary-text {
    color: #c9a66b;
  }
}
</style>
