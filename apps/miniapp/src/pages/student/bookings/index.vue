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

    <!-- AI 智能助手 -->
    <AiAssistant :session-id="'student_' + (userId || 'default')" />
  </view>
</template>

<script setup lang="ts">
import { bookingApi, tenantApi } from "@/api";
import AiAssistant from "@/components/AiAssistant.vue";
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

const systemInfo = uni.getSystemInfoSync();
const navbarHeight = systemInfo.statusBarHeight + 44;
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

  loadBookings();
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
</style>
