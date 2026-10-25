<template>
  <view class="booking-history-page">
    <AppNavbar title="预约记录" :show-back="true" variant="default" />

    <view class="main-content">
      <!-- 筛选标签 -->
      <view class="filter-tabs">
        <view
          v-for="tab in filterTabs"
          :key="tab.value"
          class="filter-tab"
          :class="{ 'filter-tab-active': activeFilter === tab.value }"
          @tap="handleFilterChange(tab.value)"
        >
          <text class="tab-text">{{ tab.label }}</text>
        </view>
      </view>

      <!-- 预约列表 -->
      <scroll-view
        scroll-y
        class="booking-list"
        :style="{ height: scrollViewHeight + 'px' }"
        :show-scrollbar="false"
        @scrolltolower="onScrollToLower"
      >
        <!-- 空状态 -->
        <view v-if="bookings.length === 0" class="empty-state">
          <AppIcon name="calendar-empty" :size="120" color="#d0c0b0" />
          <text class="empty-text">暂无预约记录</text>
        </view>

        <!-- 预约卡片列表 -->
        <view class="booking-list-inner">
          <view
            v-for="(booking, index) in bookings"
            :key="booking.id || index"
            class="booking-card"
            :style="{ animationDelay: `${index * 0.04}s` }"
          >
            <view class="card-main">
              <!-- 中间信息 -->
              <view class="card-info">
                <view class="info-top">
                  <text class="course-name">{{
                    booking.course_name || "未知课程"
                  }}</text>
                  <view
                    class="status-badge"
                    :class="
                      getStatusBadgeClass(
                        booking.display_status || booking.status,
                      )
                    "
                  >
                    <AppIcon name="check-circle" :size="24" color="#b8956a" />
                    <text class="status-text">{{
                      getStatusText(booking.display_status || booking.status)
                    }}</text>
                  </view>
                </view>

                <view class="info-row">
                  <AppIcon name="calendar" :size="28" color="#b8956a" />
                  <text class="info-text">{{
                    formatBookingDate(booking.start_at)
                  }}</text>
                </view>

                <view class="info-row">
                  <AppIcon name="location" :size="28" color="#b8956a" />
                  <text class="info-text">{{
                    booking.classroom_name || "未安排"
                  }}</text>
                </view>

                <view class="info-row">
                  <AppIcon name="user" :size="28" color="#b8956a" />
                  <text class="info-text">{{
                    booking.teacher_name || "未知"
                  }}</text>
                </view>
              </view>
            </view>

            <!-- F6.7 卡失效警示条：BOOKED 可换卡；CHECKED_IN 仅提示联系机构（R-6） -->
            <view
              v-if="getCardInvalidText(booking) && isAffectedStatus(booking)"
              class="card-warning"
            >
              <AppIcon name="alert" :size="24" color="#e67e22" />
              <text class="warning-text"
                >会员卡{{ getCardInvalidText(booking) }}</text
              >
              <text
                v-if="getBookingStatus(booking) === 1"
                class="warning-action"
                @tap="openSwapPopup(booking)"
                >换卡</text
              >
              <text v-else class="warning-action-warning">请联系机构处理</text>
            </view>

            <!-- 操作按钮 -->
            <view
              v-if="
                Number(booking.display_status || booking.status) === 1 &&
                canCancelBooking(booking)
              "
              class="card-actions"
            >
              <button class="cancel-btn" @tap="handleCancel(booking)">
                取消预约
              </button>
            </view>
            <view
              v-else-if="
                Number(booking.display_status || booking.status) === 1 &&
                !canCancelBooking(booking)
              "
              class="card-actions"
            >
              <text class="cancel-disabled"
                >开课前{{ cancelMinutes }}分钟内不可取消</text
              >
            </view>
          </view>
        </view>
      </scroll-view>
    </view>

    <!-- F6.7 换卡选卡弹层 -->
    <view v-if="showSwapPopup" class="swap-mask" @tap="closeSwapPopup">
      <view class="swap-popup" @tap.stop>
        <view class="swap-header">
          <text class="swap-title">选择替代会员卡</text>
          <view class="swap-close" @tap="closeSwapPopup">
            <text class="close-icon">×</text>
          </view>
        </view>

        <!-- loading -->
        <view v-if="swapLoading" class="swap-state">
          <text class="swap-state-text">加载可用会员卡中...</text>
        </view>

        <!-- error（可重试） -->
        <view v-else-if="swapError" class="swap-state">
          <text class="swap-state-text">{{ swapError }}</text>
          <text class="swap-retry" @tap="loadSwapCards">重试</text>
        </view>

        <!-- 无替代卡空态（F-4：引导联系机构） -->
        <view v-else-if="swapCards.length === 0" class="swap-empty">
          <text class="swap-empty-title">暂无可用替代卡</text>
          <text v-if="swapEmptyMessage" class="swap-empty-msg">{{
            swapEmptyMessage
          }}</text>
          <button
            v-if="contactPhone"
            class="contact-btn"
            @tap="handleContactOrg"
          >
            联系机构
          </button>
          <text v-else class="contact-text">请联系机构前台处理</text>
        </view>

        <!-- 替代卡列表（顺序即后端返回顺序，默认选中推荐卡） -->
        <scroll-view v-else scroll-y class="swap-list">
          <view
            v-for="card in swapCards"
            :key="card.id"
            class="swap-card-option"
            :class="{ 'swap-card-selected': swapSelectedId === card.id }"
            @tap="swapSelectedId = card.id"
          >
            <view class="card-option-left">
              <view
                class="card-radio"
                :class="{ 'radio-checked': swapSelectedId === card.id }"
              >
                <view
                  v-if="swapSelectedId === card.id"
                  class="radio-dot"
                ></view>
              </view>
              <view class="card-option-info">
                <text class="card-option-name">{{
                  card.product_name || getCardTypeText(card.card_type)
                }}</text>
                <text class="card-option-remaining">{{
                  getCardRemainingText(card)
                }}</text>
              </view>
            </view>
            <text class="type-badge" :class="'type-' + card.card_type">{{
              getCardTypeText(card.card_type)
            }}</text>
          </view>
        </scroll-view>

        <view
          v-if="!swapLoading && !swapError && swapCards.length > 0"
          class="swap-footer"
        >
          <button
            class="swap-confirm-btn"
            :disabled="!swapSelectedId || swapSubmitting"
            @tap="confirmSwap"
          >
            {{ swapSubmitting ? "提交中..." : "确定换卡" }}
          </button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { bookingApi, membershipApi, tenantApi } from "@/api";
import AppIcon from "@/components/AppIcon.vue";
import AppNavbar from "@/components/AppNavbar.vue";
import { checkLogin, getUserId } from "@/utils/auth";
import { nextTick, onMounted, onUnmounted, ref } from "vue";

const BOOKING_STATUS = {
  ALL: "all",
  BOOKED: 1,
  CANCELLED: 2,
  CHECKED_IN: 3,
  COMPLETED: 4,
} as const;

const activeFilter = ref<string | number>("all");
const bookings = ref<any[]>([]);
const userId = ref("");
const cancelMinutes = ref(90);

// ===== F6.7 卡失效警示与自助换卡 =====
// 失效卡集合：cardId -> 状态文案（2 已过期 / 3 已冻结 / 6 已作废）
const CARD_INVALID_STATUS_TEXT: Record<number, string> = {
  2: "已过期",
  3: "已冻结",
  6: "已作废",
};
const invalidCardMap = ref<Record<number, string>>({});

// 换卡弹层状态
const showSwapPopup = ref(false);
const swapBooking = ref<any>(null);
const swapCards = ref<any[]>([]);
const swapSelectedId = ref<number | null>(null);
const swapLoading = ref(false);
const swapError = ref("");
const swapEmptyMessage = ref("");
const swapSubmitting = ref(false);
// 幂等键：每次打开弹层生成一次，弹层内重试复用同一键（F6.5 幂等语义）
let swapIdempotencyKey = "";
// 机构联系电话（U-1：空态时懒加载 tenant/info 的 contact_phone）
const contactPhone = ref("");

const systemInfo = uni.getSystemInfoSync();
// 状态栏高度在 H5/部分设备可能为 undefined，缺省按 0 处理
const navbarHeight = (systemInfo.statusBarHeight ?? 0) + 44;
const tabbarHeight = (100 / 750) * systemInfo.windowWidth;
const scrollViewHeight = ref(
  Math.max(systemInfo.windowHeight - navbarHeight - tabbarHeight - 110, 400),
);

let isUnmounted = false;

const filterTabs = [
  { label: "全部", value: BOOKING_STATUS.ALL, icon: "grid" },
  { label: "待上课", value: BOOKING_STATUS.BOOKED, icon: "clock" },
  { label: "上课中", value: BOOKING_STATUS.CHECKED_IN, icon: "play" },
  { label: "已完成", value: BOOKING_STATUS.COMPLETED, icon: "check-circle" },
];

onMounted(async () => {
  const isLoggedIn = checkLogin("student");
  if (!isLoggedIn) return;

  userId.value = String(getUserId() || "");

  try {
    const settingsResult = await tenantApi.getSettings();
    if (settingsResult.code === 0 || settingsResult.code === 200) {
      cancelMinutes.value = settingsResult.data?.booking_cancel_minutes || 90;
    }
  } catch {
    // 使用默认值
  }

  // 并行加载：预约列表 + 我的会员卡（卡失效 join 数据源，F6.7）
  loadBookings();
  loadInvalidCards();
});

onUnmounted(() => {
  isUnmounted = true;
});

const onScrollToLower = () => {
  // 分页加载
};

const handleFilterChange = (value: string | number) => {
  activeFilter.value = value;
  loadBookings();
};

const loadBookings = async () => {
  try {
    const params: any = {
      exclude_cancelled: true,
    };

    if (activeFilter.value !== "all") {
      params.display_status = activeFilter.value;
    }

    const result = await bookingApi.list(params);

    if (isUnmounted) return;

    let extractedData: any[] = [];
    const rawData = result.data;

    if (rawData?.items && Array.isArray(rawData.items)) {
      extractedData = rawData.items;
    } else if (Array.isArray(rawData)) {
      extractedData = rawData;
    } else if (typeof rawData === "object") {
      const possibleKeys = ["list", "records", "rows", "content"];
      for (const key of possibleKeys) {
        if (Array.isArray((rawData as any)[key])) {
          extractedData = (rawData as any)[key];
          break;
        }
      }
    }

    bookings.value = [...extractedData];
    await nextTick();
  } catch (error: any) {
    uni.showToast({
      title: error.message?.substring(0, 20) || "加载失败",
      icon: "none",
      duration: 3000,
    });
  }
};

const formatBookingDate = (dateStr: string) => {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  const month = date.getMonth() + 1;
  const day = date.getDate();
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${month}月${day}日 ${hours}:${minutes}`;
};

// ===== F6.7 卡失效 join 与换卡 =====

// 加载我的会员卡并提取失效卡集合；失败静默降级为无警示（列表主功能优先）
const loadInvalidCards = async () => {
  try {
    const res = await membershipApi.getMyCards();
    const data: any = res?.data;
    const list: any[] = Array.isArray(data)
      ? data
      : Array.isArray(data?.items)
        ? data.items
        : [];
    const map: Record<number, string> = {};
    for (const card of list) {
      const text = CARD_INVALID_STATUS_TEXT[Number(card?.status)];
      if (text && card?.id != null) {
        map[Number(card.id)] = text;
      }
    }
    if (isUnmounted) return;
    invalidCardMap.value = map;
  } catch {
    if (!isUnmounted) {
      invalidCardMap.value = {};
    }
  }
};

const getBookingStatus = (booking: any): number =>
  Number(booking?.display_status || booking?.status);

// 预约所持卡是否已失效；返回失效文案（未失效返回 null）
const getCardInvalidText = (booking: any): string | null => {
  const cardId = Number(booking?.membership_card_id);
  if (!cardId) return null;
  return invalidCardMap.value[cardId] || null;
};

// 警示条仅针对 BOOKED(1)/CHECKED_IN(3)（K1 口径）
const isAffectedStatus = (booking: any): boolean => {
  const status = getBookingStatus(booking);
  return status === 1 || status === 3;
};

// 打开换卡弹层：生成幂等键并拉取替代卡（recommend-card，F6.6）
const openSwapPopup = (booking: any) => {
  swapBooking.value = booking;
  swapCards.value = [];
  swapSelectedId.value = null;
  swapError.value = "";
  swapEmptyMessage.value = "";
  swapIdempotencyKey = `swap-${booking.id}-${Date.now().toString(36)}-${Math.random()
    .toString(36)
    .slice(2, 8)}`;
  showSwapPopup.value = true;
  loadSwapCards();
};

const closeSwapPopup = () => {
  if (swapSubmitting.value) return;
  showSwapPopup.value = false;
  swapBooking.value = null;
};

const loadSwapCards = async () => {
  const booking = swapBooking.value;
  if (!booking?.schedule_id) {
    swapError.value = "预约信息异常，请稍后重试";
    return;
  }
  swapLoading.value = true;
  swapError.value = "";
  try {
    const res = await membershipApi.getRecommendCard(booking.schedule_id);
    const data: any = res?.data;
    swapCards.value = Array.isArray(data?.available_cards)
      ? data.available_cards
      : [];
    swapSelectedId.value =
      data?.recommended_card_id ?? swapCards.value[0]?.id ?? null;
    swapEmptyMessage.value = data?.message || "";
    if (swapCards.value.length === 0) {
      loadContactPhone();
    }
  } catch {
    swapCards.value = [];
    swapError.value = "加载失败，请重试";
  } finally {
    swapLoading.value = false;
  }
};

// 确认换卡：同排期纯改派（K3），携带幂等键；400/409 展示后端 msg 并停留弹层可重选
const confirmSwap = async () => {
  const booking = swapBooking.value;
  const cardId = swapSelectedId.value;
  if (!booking || !cardId || swapSubmitting.value) return;

  swapSubmitting.value = true;
  try {
    const result = await bookingApi.reschedule(
      booking.id,
      {
        new_schedule_id: booking.schedule_id,
        new_membership_card_id: cardId,
      },
      swapIdempotencyKey,
    );
    if (result.code === 0 || result.code === 200) {
      uni.showToast({ title: "换卡成功", icon: "success" });
      showSwapPopup.value = false;
      swapBooking.value = null;
      loadBookings();
      loadInvalidCards();
    }
  } catch {
    // API 层已 toast 后端 msg；停留弹层允许重选（D-8）
  } finally {
    swapSubmitting.value = false;
  }
};

// U-1：懒加载机构联系电话（既有 tenant/info 能力，不新增后端）
const loadContactPhone = async () => {
  if (contactPhone.value) return;
  try {
    const res = await tenantApi.getInfo();
    const data: any = res?.data;
    contactPhone.value = data?.contact_phone || "";
  } catch {
    contactPhone.value = "";
  }
};

const handleContactOrg = () => {
  if (!contactPhone.value) return;
  uni.makePhoneCall({
    phoneNumber: contactPhone.value,
    fail: () => {},
  });
};

const getCardTypeText = (type: string) => {
  const map: Record<string, string> = {
    count: "次卡",
    period: "期卡",
    unlimited: "无限卡",
  };
  return map[type] || "会员卡";
};

const getCardRemainingText = (card: any): string => {
  if (card.card_type === "count") {
    return `剩余 ${card.remaining_credits ?? 0} 次`;
  }
  if (card.card_type === "period") {
    if (!card.expire_at) return "有效期内";
    const d = new Date(card.expire_at);
    return `有效期至 ${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }
  return "不限次数";
};

const formatBookingTime = (dateStr: string) => {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${hours}:${minutes}`;
};

const getStatusBadgeClass = (status: number | string) => {
  const statusNum = Number(status);
  if (statusNum === 4) return "status-completed";
  if (statusNum === 3) return "status-in-progress";
  if (statusNum === 1) return "status-booked";
  return "status-booked";
};

const getStatusText = (status: number | string) => {
  const statusNum = Number(status);
  switch (statusNum) {
    case 1:
      return "待上课";
    case 2:
      return "已取消";
    case 3:
      return "上课中";
    case 4:
      return "已完成";
    default:
      return "待上课";
  }
};

const canCancelBooking = (booking: any): boolean => {
  if (!booking.start_at) return true;
  const startTime = new Date(booking.start_at).getTime();
  const now = Date.now();
  const minutesBefore = (startTime - now) / (1000 * 60);
  return minutesBefore > cancelMinutes.value;
};

const handleCancel = async (booking: any) => {
  uni.showModal({
    title: "确认取消",
    content: "确定要取消此预约吗？",
    success: async (res) => {
      if (res.confirm) {
        try {
          const result = await bookingApi.cancel(booking.id);
          if (result.code === 0 || result.code === 200) {
            uni.showToast({ title: "取消成功", icon: "success" });
            loadBookings();
          } else {
            uni.showToast({ title: result.msg || "取消失败", icon: "none" });
          }
        } catch {
          uni.showToast({ title: "取消失败", icon: "none" });
        }
      }
    },
  });
};
</script>

<style lang="scss" scoped>
@import "@/styles/theme/_variables.scss";
@import "@/styles/theme/_mixins.scss";

.booking-history-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: linear-gradient(180deg, #faf6f0 0%, #f5efe6 100%);
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: $space-md;
  padding-top: 0;
  min-height: 0;
}

// 筛选标签
.filter-tabs {
  display: flex;
  gap: 16rpx;
  padding: 20rpx 0;
  overflow-x: auto;
  white-space: nowrap;

  &::-webkit-scrollbar {
    display: none;
  }
}

.filter-tab {
  display: flex;
  align-items: center;
  gap: 12rpx;
  padding: 16rpx 32rpx;
  border-radius: 44rpx;
  background: #fff;
  border: 1rpx solid rgba(201, 166, 107, 0.15);
  flex-shrink: 0;
  transition: all 0.2s ease;

  &:active {
    transform: scale(0.96);
  }

  &.filter-tab-active {
    background: linear-gradient(135deg, #d4b896, #c9a66b);
    border-color: transparent;
    box-shadow: 0 4rpx 16rpx rgba(201, 166, 107, 0.3);
  }
}

.tab-text {
  font-size: 28rpx;
  color: #b8956a;
  font-weight: 500;

  .filter-tab-active & {
    color: #fff;
  }
}

// 预约列表
.booking-list {
  flex: 1;
  min-height: 0;
  padding-bottom: 180rpx;
}

.booking-list-inner {
  min-height: 100%;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 120rpx 0;
}

.empty-text {
  font-size: 28rpx;
  color: #a09080;
  margin-top: 24rpx;
}

// 预约卡片
.booking-card {
  background: #fff;
  border-radius: 24rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 4rpx 20rpx rgba(201, 166, 107, 0.08);
  overflow: hidden;
  animation: cardFadeIn 0.35s cubic-bezier(0.22, 0.61, 0.36, 1) both;
}

.card-main {
  display: flex;
  padding: 28rpx;
  position: relative;
}

.card-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.info-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.course-name {
  font-size: 32rpx;
  font-weight: 600;
  color: #5a4a3a;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 8rpx;
  padding: 8rpx 20rpx;
  border-radius: 24rpx;
  background: rgba(201, 166, 107, 0.1);
}

.status-text {
  font-size: 24rpx;
  color: #b8956a;
  font-weight: 500;
}

.info-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.info-text {
  font-size: 26rpx;
  color: #8a7a6a;
}

// 操作按钮
.card-actions {
  padding: 0 28rpx 24rpx;
}

.cancel-btn {
  width: 100%;
  height: 72rpx;
  border-radius: 36rpx;
  border: 1rpx solid rgba(231, 76, 60, 0.3);
  background: rgba(231, 76, 60, 0.08);
  color: #e74c3c;
  font-size: 28rpx;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;

  &::after {
    border: none;
  }

  &:active {
    transform: scale(0.96);
    opacity: 0.85;
  }
}

.cancel-disabled {
  display: block;
  text-align: center;
  font-size: 24rpx;
  color: #a09080;
  opacity: 0.7;
}

@keyframes cardFadeIn {
  from {
    opacity: 0;
    transform: translateY(20rpx);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

// ===== F6.7 卡失效警示条 =====
.card-warning {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin: 0 28rpx 24rpx;
  padding: 16rpx 20rpx;
  border-radius: 16rpx;
  background: rgba(230, 126, 34, 0.08);
  border: 1rpx solid rgba(230, 126, 34, 0.25);
}

.warning-text {
  flex: 1;
  font-size: 24rpx;
  color: #d35400;
}

.warning-action {
  font-size: 26rpx;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #d4b896, #c9a66b);
  padding: 10rpx 32rpx;
  border-radius: 32rpx;

  &:active {
    transform: scale(0.95);
    opacity: 0.85;
  }
}

.warning-action-warning {
  font-size: 24rpx;
  color: #a09080;
}

// ===== F6.7 换卡弹层 =====
.swap-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 100;
  display: flex;
  align-items: flex-end;
}

.swap-popup {
  width: 100%;
  max-height: 70vh;
  background: #fff;
  border-radius: 32rpx 32rpx 0 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.swap-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 32rpx 32rpx 16rpx;
}

.swap-title {
  font-size: 32rpx;
  font-weight: 600;
  color: #5a4a3a;
}

.swap-close {
  padding: 8rpx 16rpx;
}

.close-icon {
  font-size: 44rpx;
  color: #a09080;
  line-height: 1;
}

.swap-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20rpx;
  padding: 80rpx 32rpx;
}

.swap-state-text {
  font-size: 26rpx;
  color: #8a7a6a;
}

.swap-retry {
  font-size: 26rpx;
  font-weight: 600;
  color: #c9a66b;
  padding: 12rpx 48rpx;
  border: 1rpx solid rgba(201, 166, 107, 0.4);
  border-radius: 36rpx;

  &:active {
    opacity: 0.7;
  }
}

.swap-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16rpx;
  padding: 80rpx 48rpx;
}

.swap-empty-title {
  font-size: 30rpx;
  font-weight: 600;
  color: #5a4a3a;
}

.swap-empty-msg {
  font-size: 24rpx;
  color: #8a7a6a;
  text-align: center;
}

.contact-btn {
  margin-top: 16rpx;
  width: 320rpx;
  height: 80rpx;
  border-radius: 40rpx;
  background: linear-gradient(135deg, #d4b896, #c9a66b);
  color: #fff;
  font-size: 28rpx;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;

  &::after {
    border: none;
  }

  &:active {
    opacity: 0.85;
  }
}

.contact-text {
  margin-top: 16rpx;
  font-size: 26rpx;
  color: #a09080;
}

.swap-list {
  max-height: 50vh;
  padding: 0 32rpx;
}

.swap-card-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 28rpx 24rpx;
  border-radius: 20rpx;
  border: 1rpx solid rgba(201, 166, 107, 0.15);
  margin-bottom: 20rpx;
  background: #fff;

  &.swap-card-selected {
    border-color: #c9a66b;
    background: rgba(201, 166, 107, 0.06);
  }
}

.card-option-left {
  display: flex;
  align-items: center;
  gap: 20rpx;
  flex: 1;
  min-width: 0;
}

.card-radio {
  width: 36rpx;
  height: 36rpx;
  border-radius: 50%;
  border: 2rpx solid rgba(201, 166, 107, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  &.radio-checked {
    border-color: #c9a66b;
  }
}

.radio-dot {
  width: 18rpx;
  height: 18rpx;
  border-radius: 50%;
  background: #c9a66b;
}

.card-option-info {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
  min-width: 0;
}

.card-option-name {
  font-size: 28rpx;
  font-weight: 600;
  color: #5a4a3a;
}

.card-option-remaining {
  font-size: 24rpx;
  color: #8a7a6a;
}

.type-badge {
  font-size: 22rpx;
  padding: 6rpx 16rpx;
  border-radius: 20rpx;
  flex-shrink: 0;

  &.type-count {
    background: rgba(64, 158, 255, 0.12);
    color: #409eff;
  }

  &.type-period {
    background: rgba(103, 194, 58, 0.12);
    color: #67c23a;
  }

  &.type-unlimited {
    background: rgba(230, 162, 60, 0.12);
    color: #e6a23c;
  }
}

.swap-footer {
  padding: 24rpx 32rpx 40rpx;
}

.swap-confirm-btn {
  width: 100%;
  height: 88rpx;
  border-radius: 44rpx;
  background: linear-gradient(135deg, #d4b896, #c9a66b);
  color: #fff;
  font-size: 30rpx;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;

  &::after {
    border: none;
  }

  &:disabled {
    opacity: 0.5;
  }

  &:active {
    opacity: 0.85;
  }
}
</style>
