<template>
  <view class="schedule-container">
    <AppNavbar title="" :show-back="false" variant="default">
      <template #left>
        <view>排期列表</view>
      </template>
    </AppNavbar>

    <view class="main-content">
      <!-- 分类筛选栏 -->
      <scroll-view scroll-x class="filter-scroll" :show-scrollbar="false">
        <view class="filter-list">
          <view
            v-for="tab in filterTabs"
            :key="tab.value"
            class="filter-pill"
            :class="{ 'pill-active': selectedCategory === tab.value }"
            @tap="handleCategoryClick(tab.value)"
          >
            <text>{{ tab.label }}</text>
          </view>
        </view>
      </scroll-view>

      <!-- 日期选择栏 -->
      <scroll-view scroll-x class="date-scroll" :show-scrollbar="false">
        <view class="date-list">
          <view
            v-for="day in dateList"
            :key="day.date"
            class="date-pill"
            :class="{ 'pill-active': selectedDate === day.date }"
            @tap="selectDate(day.date)"
          >
            <text class="pill-day-name">{{ day.name }}</text>
            <text class="pill-day-date">{{ day.dateStr }}</text>
          </view>
        </view>
      </scroll-view>

      <scroll-view
        scroll-y
        class="schedule-scroll"
        :style="{ height: scrollViewHeight + 'px' }"
        :show-scrollbar="false"
      >
        <view v-if="loading" class="loading-state">
          <text class="loading-text">加载中...</text>
        </view>
        <view v-else-if="displaySchedules.length === 0" class="empty-state">
          <image
            :src="emptyScheduleIcon"
            mode="aspectFit"
            class="empty-illustration-img"
          />
          <text class="empty-title">暂无排期</text>
          <text class="empty-desc">您还没有相关的课程安排</text>
        </view>

        <view
          v-else
          v-for="(schedule, index) in displaySchedules"
          :key="schedule._key"
          class="schedule-card"
          :style="{ animationDelay: `${index * 0.04}s` }"
        >
          <view class="schedule-time-section">
            <text class="time-start">{{ schedule._startTime }}</text>
            <view class="time-divider"></view>
            <text class="time-end">{{ schedule._endTime }}</text>
          </view>

          <view class="schedule-content">
            <view class="schedule-top">
              <view
                class="course-type-tag"
                :class="getCourseTypeClass(schedule)"
              >
                <text>{{ getCourseTypeLabel(schedule) }}</text>
              </view>
              <text class="course-name"
                >{{
                  schedule.preview_content || schedule.course_name || "未知课程"
                }}
              </text>
              <AppIcon name="arrow-right" :size="32" color="#c9a66b" />
            </view>

            <view class="schedule-info">
              <view class="info-item">
                <AppIcon name="location" :size="28" color="#b8a088" />
                <text class="info-text"
                  >{{ schedule.classroom_name || "未安排教室" }}
                </text>
              </view>
              <view class="info-item">
                <AppIcon name="user" :size="28" color="#b8a088" />
                <text class="info-text"
                  >{{ schedule.teacher_name || "未知" }}
                </text>
              </view>
            </view>

            <view class="schedule-footer">
              <view class="capacity-info">
                <AppIcon name="people" :size="28" color="#b8a088" />
                <text class="capacity-text"
                  >{{ schedule.booked_count }}/{{ schedule.capacity }}人
                </text>
              </view>
              <view class="btn-wrapper">
                <button
                  class="book-btn"
                  :class="{
                    disabled: schedule._isDisabled,
                    booked: schedule._isBooked,
                    'no-card': schedule._statusClass === 'no_card',
                    'not-applicable':
                      schedule._statusClass === 'not_applicable',
                    insufficient: schedule._statusClass === 'insufficient',
                    'weekly-limit': schedule._statusClass === 'weekly_limit',
                  }"
                  :disabled="schedule._isDisabled"
                  @tap="
                    schedule._isBooked
                      ? handleBooking(schedule.id)
                      : openCardSelector(schedule.id)
                  "
                >
                  {{ schedule._btnText }}
                </button>
                <text v-if="schedule._cancelHint" class="cancel-hint"
                  >{{ schedule._cancelHint }}
                </text>
              </view>
            </view>
          </view>
        </view>
      </scroll-view>
    </view>

    <HomeTabBar currentRoute="/pages/student/schedule/index" />
    <AiAssistant :session-id="'student_' + (userId || 'default')" />
  </view>
</template>

<script setup lang="ts">
import { bookingApi, courseTypeApi, membershipApi, scheduleApi } from "@/api";
import AiAssistant from "@/components/AiAssistant.vue";
import AppNavbar from "@/components/AppNavbar.vue";
import HomeTabBar from "@/components/HomeTabBar.vue";
import { iconSvgMap } from "@/static/icons/icon-map";
import { checkLogin } from "@/utils/auth";
import {
  formatTime,
  isScheduleExpired,
  isWithinBookingWindow,
  toAPIDateTime,
} from "@/utils/date";
import { extractList } from "@/utils/helpers";
import { computed, nextTick, onMounted, onUnmounted, ref } from "vue";

const emptyScheduleIcon = computed(() => {
  const svg = iconSvgMap["empty-schedule"];
  const encoded = encodeURIComponent(svg);
  return `data:image/svg+xml,${encoded}`;
});

const filterTabs = ref<Array<{ label: string; value: string }>>([
  { label: "全部", value: "all" },
]);
const selectedCategory = ref("all");
const selectedDate = ref("");
const daySchedules = ref<any[]>([]);
const bookings = ref<any[]>([]);
const loading = ref(false);
const userId = ref("");
const cancelMinutes = ref(90); // 默认90分钟

// 会员卡相关
const membershipCards = ref<any[]>([]);
const isLoadingCards = ref(false);

interface CardValidationResult {
  valid: boolean;
  availableCards: any[];
  reason?: string;
  reasonType?:
    | "no_card"
    | "not_applicable"
    | "insufficient"
    | "weekly_limit"
    | "expired";
}

const systemInfo = uni.getSystemInfoSync();
const navbarHeight = systemInfo.statusBarHeight + 44;
const tabbarHeight = (100 / 750) * systemInfo.windowWidth;
const filterAreaHeight = (280 / 750) * systemInfo.windowWidth;
const scrollViewHeight = ref(
  Math.max(
    systemInfo.windowHeight - navbarHeight - tabbarHeight - filterAreaHeight,
    300,
  ),
);

let isLoadingSchedules = false;
let isLoadingBookings = false;
let debounceTimer: number | null = null;
let loadBookingsTimer: number | null = null;
let retryTimer: number | null = null;
let isUnmounted = false;
let pendingDateRefresh: string | null = null;

const dateList = computed(() => {
  const days: Array<{ date: string; name: string; dateStr: string }> = [];
  const today = new Date();
  const dayNames = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];

  for (let i = -2; i <= 14; i++) {
    const date = new Date(today);
    date.setDate(today.getDate() + i);
    const dateStr = date.toISOString().split("T")[0];
    days.push({
      date: dateStr,
      name: i === 0 ? "今日" : i === 1 ? "明日" : dayNames[date.getDay()],
      dateStr: `${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`,
    });
  }
  return days;
});

const displaySchedules = computed(() => {
  const bookedScheduleIds = new Set(
    bookings.value.map((b: any) => b.schedule_id),
  );
  const now = Date.now();

  return daySchedules.value.map((schedule: any, index: number) => {
    const isBooked = bookedScheduleIds.has(schedule.id);
    const isFull = schedule.booked_count >= schedule.capacity;
    const isExpired = isScheduleExpired(schedule.start_at);
    const isOutOfWindow = !isWithinBookingWindow(schedule.start_at, 14);

    // 计算是否在开课前限制时间内
    const startAtTime = new Date(schedule.start_at).getTime();
    const minutesBeforeStart = (startAtTime - now) / (1000 * 60);
    const isWithinCancelLimit =
      minutesBeforeStart <= cancelMinutes.value && minutesBeforeStart > 0;
    const isOngoing = minutesBeforeStart <= 0 && !isExpired;

    const isDisabled =
      isExpired ||
      isOutOfWindow ||
      (isFull && !isBooked) ||
      (isBooked && (isWithinCancelLimit || isOngoing));

    let statusText: string;
    let btnText: string;
    let statusClass: string;

    if (isBooked) {
      if (isOngoing) {
        statusText = "已预约";
        btnText = "不可取消";
        statusClass = "booked";
      } else if (isWithinCancelLimit) {
        statusText = "已预约";
        btnText = "不可取消";
        statusClass = "booked";
      } else {
        statusText = "已预约";
        btnText = "取消";
        statusClass = "booked";
      }
    } else if (isExpired) {
      statusText = "已完成";
      btnText = "已完成";
      statusClass = "completed";
    } else if (isOutOfWindow) {
      statusText = "不可预约";
      btnText = "不可预约";
      statusClass = "disabled";
    } else if (isFull) {
      statusText = "已满";
      btnText = "已满";
      statusClass = "full";
    } else {
      // 检查会员卡状态
      const cardValidation = validateCardForSchedule(schedule);
      if (!cardValidation.valid) {
        switch (cardValidation.reasonType) {
          case "no_card":
            statusText = "无会员卡";
            btnText = "无会员卡";
            statusClass = "no_card";
            break;
          case "not_applicable":
            statusText = "不适用";
            btnText = "不适用";
            statusClass = "not_applicable";
            break;
          case "insufficient":
            statusText = "余额不足";
            btnText = "余额不足";
            statusClass = "insufficient";
            break;
          case "weekly_limit":
            statusText = "已达上限";
            btnText = "已达上限";
            statusClass = "weekly_limit";
            break;
          default:
            statusText = "可预约";
            btnText = "预约";
            statusClass = "available";
        }
      } else {
        statusText = "可预约";
        btnText = "预约";
        statusClass = "available";
      }
    }

    // 取消提示文案
    let cancelHint: string = "";
    if (isBooked && isOngoing) {
      cancelHint = "课程已开始，不可取消";
    } else if (isBooked && isWithinCancelLimit) {
      cancelHint = `开课前${cancelMinutes.value}分钟内不可取消`;
    }

    return {
      ...schedule,
      _key: schedule.id || `schedule-${selectedDate.value}-${index}`,
      _startTime: formatTime(schedule.start_at),
      _endTime: formatTime(schedule.end_at),
      _isBooked: isBooked,
      _isFull: isFull,
      _isDisabled:
        isDisabled ||
        (!isBooked &&
          !isExpired &&
          !isOutOfWindow &&
          !isFull &&
          !validateCardForSchedule(schedule).valid),
      _statusClass: statusClass,
      _statusText: statusText,
      _btnText: btnText,
      _isWithinCancelLimit: isWithinCancelLimit,
      _isOngoing: isOngoing,
      _cancelHint: cancelHint,
      _cardValidation:
        !isBooked && !isExpired && !isOutOfWindow && !isFull
          ? validateCardForSchedule(schedule)
          : null,
    };
  });
});

// 会员卡验证函数
const validateCardForSchedule = (schedule: any): CardValidationResult => {
  if (membershipCards.value.length === 0) {
    return {
      valid: false,
      availableCards: [],
      reason: "您需要先办理会员卡才能预约课程",
      reasonType: "no_card",
    };
  }

  // 筛选有效会员卡
  const now = new Date();
  const validCards = membershipCards.value.filter((card: any) => {
    if (card.status !== 1) return false; // 1 = ACTIVE

    // 检查有效期
    if (card.expire_at && new Date(card.expire_at) < now) return false;
    if (card.valid_from && new Date(card.valid_from) > now) return false;

    // 检查次卡余额
    if (card.card_type === "count") {
      const remaining = (card.total_credits || 0) - (card.used_credits || 0);
      if (remaining <= 0) return false;
    }

    return true;
  });

  if (validCards.length === 0) {
    // 检查是否有卡但都无效
    const hasExpiredCards = membershipCards.value.some((card: any) => {
      if (card.status === 1 && card.expire_at && new Date(card.expire_at) < now)
        return true;
      if (card.status === 1 && card.card_type === "count") {
        const remaining = (card.total_credits || 0) - (card.used_credits || 0);
        if (remaining <= 0) return true;
      }
      return false;
    });

    if (hasExpiredCards) {
      return {
        valid: false,
        availableCards: [],
        reason: "您的会员卡已过期或余额不足，请续费",
        reasonType: "expired",
      };
    }

    return {
      valid: false,
      availableCards: [],
      reason: "您需要先办理会员卡才能预约课程",
      reasonType: "no_card",
    };
  }

  // 检查适用课程类型（单选字段）
  const scheduleCourseTypeCode = schedule.course_type_code;
  const typeApplicableCards = validCards.filter((card: any) => {
    const cardCourseType = card.applicable_course_type_code;

    if (!cardCourseType) {
      return true; // 适用于所有课程类型
    }
    if (!scheduleCourseTypeCode) return true;
    return cardCourseType === scheduleCourseTypeCode;
  });

  if (typeApplicableCards.length === 0) {
    return {
      valid: false,
      availableCards: [],
      reason: "当前会员卡不适用于此课程类型",
      reasonType: "not_applicable",
    };
  }

  // 检查适用课程
  const applicableCards = typeApplicableCards.filter((card: any) => {
    if (
      !card.applicable_course_ids ||
      card.applicable_course_ids.length === 0
    ) {
      return true; // 适用于所有课程
    }
    return card.applicable_course_ids.includes(schedule.course_id);
  });

  if (applicableCards.length === 0) {
    return {
      valid: false,
      availableCards: [],
      reason: "当前会员卡不适用于此课程",
      reasonType: "not_applicable",
    };
  }

  // 检查每周使用次数限制
  const cardsWithinWeeklyLimit = applicableCards.filter((card: any) => {
    if (!card.max_weekly_usage) return true; // 无限制

    // TODO: 需要后端API支持查询本周使用次数
    // 暂时假设未超限
    return true;
  });

  if (cardsWithinWeeklyLimit.length === 0) {
    return {
      valid: false,
      availableCards: [],
      reason: "本周使用次数已达上限",
      reasonType: "weekly_limit",
    };
  }

  return {
    valid: true,
    availableCards: cardsWithinWeeklyLimit,
  };
};

// 加载会员卡
const loadMembershipCards = async () => {
  if (isLoadingCards.value) return;
  isLoadingCards.value = true;

  try {
    const result = await membershipApi.getMyCards();
    if (isUnmounted) return;

    const responseData = result?.data as any;
    let cards: any[] = [];

    if (responseData?.items && Array.isArray(responseData.items)) {
      cards = responseData.items;
    } else if (Array.isArray(responseData)) {
      cards = responseData;
    }

    membershipCards.value = cards;
  } catch (error) {
    console.error("加载会员卡失败:", error);
  } finally {
    isLoadingCards.value = false;
  }
};

// 打开预约确认页
const openCardSelector = (scheduleId: number) => {
  const schedule = daySchedules.value.find((s: any) => s.id === scheduleId);
  if (!schedule) return;

  const validation = validateCardForSchedule(schedule);
  if (!validation.valid) {
    uni.showToast({
      title: validation.reason || "无法预约",
      icon: "none",
      duration: 2000,
    });
    return;
  }

  // 跳转到预约确认页
  uni.navigateTo({
    url: `/pages/student/booking-confirm/index?scheduleId=${scheduleId}`,
  });
};

onMounted(async () => {
  if (!checkLogin("student")) return;

  const userInfo = uni.getStorageSync("user_info");
  if (userInfo) {
    try {
      const parsed = JSON.parse(userInfo);
      userId.value = parsed.id || "";
    } catch {}
  }

  // 加载租户配置
  try {
    const settingsResult = await tenantApi.getSettings();
    if (settingsResult.code === 0 || settingsResult.code === 200) {
      cancelMinutes.value = settingsResult.data?.booking_cancel_minutes || 90;
      console.log(
        "✅ 租户配置加载成功，取消时间限制:",
        cancelMinutes.value,
        "分钟",
      );
    }
  } catch (error) {
    console.warn("⚠️ 加载租户配置失败，使用默认值90分钟:", error);
  }

  const today = new Date().toISOString().split("T")[0];
  selectedDate.value = today;
  loadCourseTypes();
  loadSchedules();
  loadBookings();
  loadMembershipCards();

  uni.$on("bookingSuccess", handleBookingSuccess);
});

const loadCourseTypes = async () => {
  try {
    const result = await courseTypeApi.list({ status: 1 });
    if (isUnmounted) return;

    const responseData = result?.data as any;
    let items: any[] = [];

    if (responseData?.items && Array.isArray(responseData.items)) {
      items = responseData.items;
    } else if (Array.isArray(responseData)) {
      items = responseData;
    }

    // 构建 filter tabs，使用课程类型名称作为显示标签
    const tabs: Array<{ label: string; value: string }> = [
      { label: "全部", value: "all" },
    ];

    items.forEach((type: any) => {
      if (type.code && type.status === 1) {
        tabs.push({ label: type.name, value: type.code });
      }
    });

    filterTabs.value = tabs;
  } catch (error) {
    console.error("加载课程类型失败:", error);
  }
};

const goToBookCourse = () => {
  uni.switchTab({ url: "/pages/student/course/index" });
};

onUnmounted(() => {
  isUnmounted = true;
  if (debounceTimer) {
    clearTimeout(debounceTimer);
    debounceTimer = null;
  }
  if (loadBookingsTimer) {
    clearTimeout(loadBookingsTimer);
    loadBookingsTimer = null;
  }
  if (retryTimer) {
    clearTimeout(retryTimer);
    retryTimer = null;
  }
  uni.$off("bookingSuccess", handleBookingSuccess);
});

const loadSchedules = async () => {
  if (isLoadingSchedules) {
    pendingDateRefresh = selectedDate.value;
    return;
  }

  isLoadingSchedules = true;
  loading.value = true;

  try {
    const apiDateTime = toAPIDateTime(selectedDate.value);
    const params: any = {
      start_from: apiDateTime.start,
      start_to: apiDateTime.end,
      status: 1,
    };
    if (selectedCategory.value !== "all") {
      params.course_type_code = selectedCategory.value;
    }

    const result = await scheduleApi.list(params);
    if (isUnmounted) return;

    const responseData = result?.data as any;
    let finalList: any[] = [];

    if (responseData?.items && Array.isArray(responseData.items)) {
      finalList = responseData.items;
    } else if (Array.isArray(responseData)) {
      finalList = responseData;
    } else {
      finalList = extractList(result);
    }

    daySchedules.value = finalList;
    loading.value = false;
    await nextTick();

    loadBookingsTimer = setTimeout(() => {
      loadBookings();
      loadBookingsTimer = null;
    }, 150) as unknown as number;
  } catch (error) {
    console.error("加载排期失败:", error);
    uni.showToast({ title: "加载失败", icon: "none" });
    isLoadingSchedules = false;
    loading.value = false;
  }
};

const onAllDataLoaded = () => {
  isLoadingSchedules = false;
  if (pendingDateRefresh && pendingDateRefresh !== selectedDate.value) {
    const refreshDate = pendingDateRefresh;
    pendingDateRefresh = null;
    retryTimer = setTimeout(() => {
      loadSchedules();
      retryTimer = null;
    }, 50) as unknown as number;
  }
};

const loadBookings = async () => {
  if (isLoadingBookings) return;
  isLoadingBookings = true;

  try {
    const result = await bookingApi.list({ status: 1 });
    if (isUnmounted) return;

    const responseData = result?.data as any;
    let finalList: any[] = [];

    if (responseData?.items && Array.isArray(responseData.items)) {
      finalList = responseData.items;
    } else if (Array.isArray(responseData)) {
      finalList = responseData;
    } else {
      finalList = extractList(result);
    }

    bookings.value = finalList;
  } catch (error) {
    console.error("加载预约失败:", error);
  } finally {
    isLoadingBookings = false;
    onAllDataLoaded();
  }
};

const handleCategoryClick = (value: string) => {
  if (value === selectedCategory.value) return;
  selectedCategory.value = value;
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    loadSchedules();
    debounceTimer = null;
  }, 100) as unknown as number;
};

const selectDate = (date: string) => {
  if (date === selectedDate.value) return;
  selectedDate.value = date;

  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    loadSchedules();
    debounceTimer = null;
  }, 100) as unknown as number;
};

const isScheduleBooked = (scheduleId: number): boolean => {
  return bookings.value.some(
    (booking: any) => booking.schedule_id === scheduleId,
  );
};

const getCourseTypeLabel = (schedule: any): string => {
  const typeMap: Record<string, string> = {
    private: "私教课",
    regular: "常规课",
    special: "特色课",
  };
  return (
    typeMap[schedule.course_type_code] || schedule.course_type_name || "常规课"
  );
};

const getCourseTypeClass = (schedule: any): string => {
  const typeMap: Record<string, string> = {
    private: "tag-private",
    regular: "tag-regular",
    special: "tag-special",
  };
  return typeMap[schedule.course_type_code] || "tag-regular";
};

const handleBooking = async (scheduleId: number) => {
  const schedule = daySchedules.value.find((s: any) => s.id === scheduleId);
  if (!schedule) {
    uni.showToast({ title: "排期不存在", icon: "none" });
    return;
  }

  if (isScheduleExpired(schedule.start_at)) {
    uni.showToast({ title: "该课程已过期，无法预约", icon: "none" });
    return;
  }

  if (!isWithinBookingWindow(schedule.start_at, 14)) {
    uni.showToast({ title: "仅可预约两周内的课程", icon: "none" });
    return;
  }

  // 已预约的课程，检查是否在取消时间限制内或课程进行中
  if (isScheduleBooked(scheduleId)) {
    if (schedule._isWithinCancelLimit) {
      uni.showModal({
        title: "无法取消",
        content: `开课前${cancelMinutes.value}分钟内不可取消预约，请准时参加课程`,
        showCancel: false,
        confirmText: "知道了",
      });
      return;
    }

    if (schedule._isOngoing) {
      uni.showModal({
        title: "无法取消",
        content: "课程已开始，不可取消预约",
        showCancel: false,
        confirmText: "知道了",
      });
      return;
    }

    uni.showModal({
      title: "取消预约",
      content: "确定要取消此预约吗？",
      success: async (res) => {
        if (res.confirm) await cancelBooking(scheduleId);
      },
    });
    return;
  }

  // 跳转到预约确认页
  uni.navigateTo({
    url: `/pages/student/booking-confirm/index?scheduleId=${scheduleId}`,
  });
};

const cancelBooking = async (scheduleId: number) => {
  try {
    const booking = bookings.value.find(
      (b: any) => b.schedule_id === scheduleId,
    );
    if (!booking) {
      uni.showToast({ title: "未找到预约记录", icon: "none" });
      return;
    }

    if (booking.start_at) {
      const startTime = new Date(booking.start_at).getTime();
      const now = Date.now();
      const minutesBefore = (startTime - now) / (1000 * 60);
      if (minutesBefore <= cancelMinutes.value) {
        uni.showToast({
          title: `开课前${cancelMinutes.value}分钟内不可取消`,
          icon: "none",
        });
        return;
      }
    }

    const result = await bookingApi.cancel(booking.id);
    if (result.code === 0 || result.code === 200) {
      uni.showToast({ title: "取消成功", icon: "success" });
      await Promise.all([loadSchedules(), loadBookings()]);
    } else {
      uni.showToast({ title: result.msg || "取消失败", icon: "none" });
    }
  } catch {
    uni.showToast({ title: "取消失败", icon: "none" });
  }
};

const handleBookingSuccess = async () => {
  console.log("🎉 收到预约成功事件，刷新排期和预约数据");
  await Promise.all([loadSchedules(), loadBookings(), loadMembershipCards()]);
};
</script>

<style lang="scss">
.schedule-container {
  @include page-container;
  overflow: visible;
}

.main-content {
  @include main-content;
  overflow: visible;
  padding: $space-md $space-md $space-sm;
}

// 分类筛选栏
.filter-scroll {
  white-space: nowrap;
  margin-bottom: $space-md;
  padding: 0;
  overflow: visible;
  @include hide-scrollbar;
}

.filter-list {
  display: inline-flex;
  gap: $space-xs;
  padding: 6rpx 0;
  align-items: center;
}

// 日期选择栏
.date-scroll {
  white-space: nowrap;
  margin-bottom: $space-md;
  padding: 0;
  @include hide-scrollbar;
}

.date-list {
  display: inline-flex;
  gap: $space-xs;
  padding: 0;
  align-items: center;
}

// 分类 Pill
.filter-pill {
  @include badge-base(20rpx 32rpx, $radius-full, $font-size-body_sm);
  background: rgba(255, 255, 255, 0.85);
  border: 2rpx solid rgba(201, 166, 107, 0.2);
  color: #8b7355;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.04);
  box-sizing: border-box;
  line-height: 1.2;
  transition: all $duration-fast $ease-standard;

  &:active {
    transform: scale(0.96);
  }

  &.pill-active {
    background: linear-gradient(135deg, #e8d5b7 0%, #d4b896 100%);
    color: #5c4a32;
    border-color: transparent;
    box-shadow: 0 4rpx 16rpx rgba(201, 166, 107, 0.3);
    font-weight: 600;
  }
}

// 日期 Pill
.date-pill {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 120rpx;
  padding: $space-sm $space-md;
  border-radius: $radius-lg;
  transition: all $duration-fast $ease-standard;
  background: rgba(255, 255, 255, 0.85);
  border: 2rpx solid rgba(201, 166, 107, 0.15);
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.04);
  position: relative;

  &:active {
    transform: scale(0.96);
  }

  &.pill-active {
    background: linear-gradient(135deg, #d4b896 0%, #c9a66b 100%);
    border-color: transparent;
    box-shadow: 0 4rpx 16rpx rgba(201, 166, 107, 0.35);

    .pill-day-name,
    .pill-day-date {
      color: #fff;
    }

    &::after {
      content: "";
      position: absolute;
      bottom: 12rpx;
      width: 8rpx;
      height: 8rpx;
      background: #fff;
      border-radius: 50%;
    }
  }
}

.pill-day-name {
  font-size: $font-size-caption;
  color: $text-tertiary;
  margin-bottom: 2rpx;
}

.pill-day-date {
  font-size: $font-size-body_sm;
  color: $text-primary;
  font-weight: $font-weight-medium;
}

.schedule-scroll {
  padding: 0;
  padding-bottom: 120rpx;
  box-sizing: border-box;

  // 完全隐藏滚动条（包括轨道）
  &::-webkit-scrollbar {
    display: none;
    width: 0;
    height: 0;
  }
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 120rpx 0;
}

.loading-text {
  font-size: $font-size-body;
  color: $text-tertiary;
}

// 空状态
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60rpx 40rpx 60rpx;
  gap: 20rpx;

  .empty-illustration-img {
    width: 420rpx;
    height: 320rpx;
    margin-bottom: 8rpx;
  }

  .empty-title {
    font-size: 32rpx;
    font-weight: 600;
    color: #5c4a32;
  }

  .empty-desc {
    font-size: 26rpx;
    color: #b8a088;
  }
}

// 去预约课程按钮
.go-book-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  padding: 20rpx 48rpx;
  background: linear-gradient(135deg, #d4b896 0%, #c9a66b 100%);
  border-radius: 50rpx;
  border: none;
  box-shadow: 0 4rpx 20rpx rgba(201, 166, 107, 0.35);
  margin-top: 12rpx;

  text {
    font-size: 28rpx;
    color: #fff;
    font-weight: 500;
  }

  .btn-arrow {
    font-size: 32rpx;
    color: #fff;
    margin-left: 4rpx;
  }

  &::after {
    border: none;
  }

  &:active {
    transform: scale(0.96);
    box-shadow: 0 2rpx 12rpx rgba(201, 166, 107, 0.4);
  }
}

.schedule-card {
  display: flex;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(20rpx);
  -webkit-backdrop-filter: blur(20rpx);
  border-radius: 24rpx;
  border: 1rpx solid rgba(201, 166, 107, 0.12);
  padding: 28rpx 24rpx;
  margin-bottom: $space-md;
  box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.04);
  transition:
    transform $duration-fast $ease-standard,
    box-shadow $duration-fast $ease-standard;
  animation: cardFadeIn 0.35s cubic-bezier(0.22, 0.61, 0.36, 1) both;
  position: relative;
  overflow: hidden;

  &::before {
    content: "";
    position: absolute;
    top: 0;
    right: 0;
    width: 200rpx;
    height: 200rpx;
    background: radial-gradient(
      circle,
      rgba(201, 166, 107, 0.06) 0%,
      transparent 70%
    );
    pointer-events: none;
  }

  &:active {
    transform: translateY(-2rpx);
    box-shadow: 0 8rpx 28rpx rgba(0, 0, 0, 0.06);
  }
}

.schedule-time-section {
  width: 100rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-right: $space-md;
  flex-shrink: 0;
  background: linear-gradient(
    180deg,
    rgba(232, 213, 183, 0.3) 0%,
    rgba(212, 184, 150, 0.15) 100%
  );
  border-radius: 16rpx;
  padding: 16rpx 12rpx;
}

.time-start,
.time-end {
  font-size: 28rpx;
  font-weight: 600;
  color: #8b7355;
  line-height: 1.2;
}

.time-divider {
  width: 2rpx;
  height: 24rpx;
  background: linear-gradient(
    180deg,
    #c9a66b 0%,
    rgba(201, 166, 107, 0.3) 100%
  );
  margin: 8rpx 0;
  border-radius: $radius-full;
}

.schedule-content {
  flex: 1;
  min-width: 0;
}

.schedule-top {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 16rpx;
}

.course-type-tag {
  padding: 4rpx 16rpx;
  border-radius: 20rpx;
  font-size: 22rpx;
  font-weight: 500;
  flex-shrink: 0;

  &.tag-private {
    background: linear-gradient(
      135deg,
      rgba(232, 213, 183, 0.5) 0%,
      rgba(212, 184, 150, 0.3) 100%
    );
    color: #8b7355;
  }

  &.tag-regular {
    background: linear-gradient(
      135deg,
      rgba(200, 180, 220, 0.4) 0%,
      rgba(180, 160, 200, 0.2) 100%
    );
    color: #7b6b8a;
  }

  &.tag-special {
    background: linear-gradient(
      135deg,
      rgba(180, 220, 200, 0.4) 0%,
      rgba(160, 200, 180, 0.2) 100%
    );
    color: #5b8a7b;
  }
}

.course-name {
  font-size: 32rpx;
  font-weight: 600;
  color: #4a3728;
  letter-spacing: 0.5rpx;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.schedule-info {
  margin-bottom: 20rpx;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 8rpx;
  margin-bottom: 8rpx;
}

.info-text {
  font-size: 26rpx;
  color: #8b7355;
  line-height: 1.4;
}

.schedule-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.capacity-info {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.capacity-text {
  font-size: 24rpx;
  color: #a89880;
}

.btn-wrapper {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: $space-2xs;
}

.cancel-hint {
  font-size: $font-size-caption;
  color: #c9a66b;
  line-height: 1.2;
}

.book-btn {
  padding: 12rpx 28rpx;
  background: linear-gradient(135deg, #c9a66b 0%, #d4b896 100%);
  color: #fff;
  border-radius: 32rpx;
  border: none;
  font-size: 24rpx;
  font-weight: 500;
  letter-spacing: 0.5rpx;
  transition: all $duration-fast $ease-standard;
  box-shadow: 0 4rpx 12rpx rgba(201, 166, 107, 0.3);
  line-height: 1.2;

  &::after {
    border: none;
  }

  &:active {
    transform: scale(0.96);
    box-shadow: 0 2rpx 8rpx rgba(201, 166, 107, 0.4);
  }

  &.disabled {
    background: #f5f0eb;
    color: #c4b5a5;
    box-shadow: none;

    &::after {
      border: none;
    }
  }

  &.booked {
    background: linear-gradient(135deg, #e8d5b7 0%, #d4b896 100%);
    color: #fff;
    font-weight: 600;
    box-shadow: 0 2rpx 8rpx rgba(201, 166, 107, 0.25);

    &::after {
      border: none;
    }

    &:active {
      background: linear-gradient(135deg, #d4b896 0%, #c9a66b 100%);
      transform: scale(0.95);
    }
  }

  &.no-card {
    background: #f5f0eb;
    color: #c4b5a5;
    box-shadow: none;
    border: 1rpx solid rgba(201, 166, 107, 0.15);

    &::after {
      border: none;
    }
  }

  &.not-applicable {
    background: rgba(232, 213, 183, 0.5);
    color: #a89880;
    box-shadow: none;
    border: 1rpx solid rgba(201, 166, 107, 0.2);

    &::after {
      border: none;
    }
  }

  &.insufficient {
    background: rgba(232, 213, 183, 0.5);
    color: #a89880;
    box-shadow: none;
    border: 1rpx solid rgba(201, 166, 107, 0.2);

    &::after {
      border: none;
    }
  }

  &.weekly-limit {
    background: rgba(232, 213, 183, 0.5);
    color: #a89880;
    box-shadow: none;
    border: 1rpx solid rgba(201, 166, 107, 0.2);

    &::after {
      border: none;
    }
  }
}

@keyframes cardFadeIn {
  from {
    opacity: 0;
    transform: translateY(8rpx);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
