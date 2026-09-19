<template>
  <view class="course-detail-page">
    <!-- 自定义导航栏 -->
    <AppNavbar title="课程详情" :show-back="true" variant="default">
    </AppNavbar>

    <!-- 封面区域 -->
    <view class="hero-section">
      <image
        :src="
          course.cover_url ||
          'https://images.unsplash.com/photo-1508700929628-666bc8bd84ea?w=800&q=80'
        "
        mode="aspectFill"
        class="hero-image"
      />
      <view class="hero-overlay"></view>
    </view>

    <!-- 主内容区域 -->
    <view class="scroll-wrapper">
      <scroll-view
        scroll-y
        class="details-content"
        :style="{ height: scrollViewHeight + 'px' }"
        :show-scrollbar="false"
        :refresher-enabled="true"
        :refresher-triggered="refreshing"
        @refresherrefresh="handleRefresh"
      >
        <!-- 课程信息统计栏 -->
        <view class="info-bar">
          <view class="info-bar-item">
            <text class="info-bar-value">{{ course.duration_minutes }}</text>
            <view class="info-bar-sub">
              <AppIcon name="clock" :size="28" color="#b8956a" />
              <text class="info-bar-label">分钟</text>
            </view>
          </view>
          <view class="info-bar-divider"></view>
          <view class="info-bar-item">
            <view class="info-bar-top">
              <AppIcon name="tag" :size="32" color="#b8956a" />
              <text class="info-bar-value-sm">{{
                course.category_name || course.category
              }}</text>
            </view>
            <text class="info-bar-label">分类</text>
          </view>
          <view class="info-bar-divider"></view>
          <view class="info-bar-item">
            <view class="info-bar-top">
              <AppIcon name="calendar" :size="32" color="#b8956a" />
              <text class="info-bar-value-sm">{{ course.level }}</text>
            </view>
            <text class="info-bar-label">级别</text>
          </view>
        </view>

        <!-- 课程简介 -->
        <view class="content-card">
          <view class="card-section-header">
            <view class="section-icon-title">
              <AppIcon name="tag" :size="44" color="#b8956a" />
              <text class="section-title">课程简介</text>
              <view class="section-line"></view>
            </view>
          </view>
          <view class="card-section-body">
            <text class="description-text">{{
              course.description || "暂无简介"
            }}</text>
          </view>
        </view>

        <!-- 上课须知 -->
        <view class="content-card">
          <view class="card-section-header">
            <view class="section-icon-title">
              <AppIcon name="calendar-check" :size="44" color="#b8956a" />
              <text class="section-title">上课须知</text>
              <view class="section-line"></view>
            </view>
          </view>
          <view class="card-section-body">
            <view class="notice-list">
              <view class="notice-item">
                <text class="notice-dot">•</text>
                <text class="notice-text">1. 课程须知</text>
              </view>
              <view class="notice-item">
                <text class="notice-dot">•</text>
                <text class="notice-text"
                  >1.
                  大课满四人开课，开课前90分钟未满四人，系统自动取消课程。</text
                >
              </view>
              <view class="notice-item">
                <text class="notice-dot">•</text>
                <text class="notice-text"
                  >2. 请提前预约课程，未约课者禁止进入教室！</text
                >
              </view>
              <view class="notice-item">
                <text class="notice-dot">•</text>
                <text class="notice-text"
                  >3.
                  提前90分钟可取消课程，请合理安排上课时间，不可临时取消！否则次卡我约扣一次，请卡费约扣一天，不可销销。</text
                >
              </view>
              <view class="notice-item">
                <text class="notice-dot">•</text>
                <text class="notice-text"
                  >4. 课程如有变动，请以约课系统为准。</text
                >
              </view>
              <view class="notice-item">
                <text class="notice-dot">•</text>
                <text class="notice-text"
                  >5. 请在预约课程开始前10分钟到达教室，请勿迟到！</text
                >
              </view>
            </view>
          </view>
        </view>

        <view class="bottom-spacer"></view>
      </scroll-view>
    </view>

    <view v-if="loading" class="loading-overlay">
      <AppLoading type="skeleton" />
    </view>

    <!-- 底部预约按钮 -->
    <view class="footer-bar">
      <button class="footer-book-btn" @tap="handleQuickBook">
        <text class="footer-btn-text">立即预约</text>
      </button>
    </view>

    <!-- AI 智能助手 -->
    <AiAssistant :session-id="'student_' + (userId || 'default')" />
  </view>
</template>

<script setup lang="ts">
import { bookingApi, courseApi, scheduleApi } from "@/api";
import AiAssistant from "@/components/AiAssistant.vue";
import AppLoading from "@/components/AppLoading.vue";
import AppNavbar from "@/components/AppNavbar.vue";
import { formatDate, formatTime } from "@/utils/date";
import { extractList } from "@/utils/helpers";
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";

const courseId = ref(0);
const userId = ref("");
const course = ref<any>({});
const schedules = ref<any[]>([]);
const myBookings = ref<any[]>([]);
const loading = ref(false);
const refreshing = ref(false);
const bookingLoading = reactive<Record<number, boolean>>({});

const systemInfo = uni.getSystemInfoSync();
const menuButton = uni.getMenuButtonBoundingClientRect();
const navbarHeight =
  systemInfo.statusBarHeight + Math.max(menuButton.height + 10, 44);
const heroHeightPx = (380 / 750) * systemInfo.windowWidth;
const footerBarHeightPx = 120; // 底部按钮区域高度
const scrollViewHeight = ref(
  Math.max(
    systemInfo.windowHeight - navbarHeight - heroHeightPx - footerBarHeightPx,
    300,
  ),
);

let isUnmounted = false;

const displaySchedules = computed(() => {
  const bookedScheduleIds = new Set(
    myBookings.value.map((b: any) => b.schedule_id),
  );

  return schedules.value.map((schedule: any, index: number) => {
    const isBooked = bookedScheduleIds.has(schedule.id);
    const isFull = schedule.booked_count >= schedule.capacity;

    return {
      ...schedule,
      _key: schedule.id || `schedule-${index}`,
      _dateText: formatDate(schedule.start_at, true),
      _startTime: formatTime(schedule.start_at),
      _endTime: formatTime(schedule.end_at),
      _isBooked: isBooked,
      _isFull: isFull,
      _isDisabled: isFull && !isBooked,
      _capacityPercent:
        schedule.capacity > 0
          ? Math.min(
              Math.round((schedule.booked_count / schedule.capacity) * 100),
              100,
            )
          : 0,
      _statusClass: isBooked ? "booked" : isFull ? "full" : "available",
      _statusText: isBooked ? "已预约" : isFull ? "已满" : "可预约",
      _btnText: isBooked ? "取消" : isFull ? "已满" : "预约",
    };
  });
});

onUnmounted(() => {
  isUnmounted = true;
});

onMounted(() => {
  console.log("=== 📚 课程详情页 - 开始初始化 ===");

  const userInfo = uni.getStorageSync("user_info");
  if (userInfo) {
    try {
      const parsed = JSON.parse(userInfo);
      userId.value = parsed.id || "";
    } catch {}
  }

  let id: number | null = null;

  try {
    const pages = getCurrentPages();
    if (pages.length > 0) {
      const currentPage = pages[pages.length - 1] as any;
      const options = currentPage?.options || {};

      if (options.id) {
        id = parseInt(options.id);
      }

      if (!id && currentPage?.id) {
        id = parseInt(currentPage.id);
      }
    }
  } catch (error) {
    console.error("❌ 获取页面参数失败:", error);
  }

  if (!id) {
    try {
      const currentPages = getCurrentPages();
      const currentRoute = currentPages[currentPages.length - 1]?.route || "";
      const urlMatch = currentRoute.match(/id=(\d+)/);
      if (urlMatch && urlMatch[1]) {
        id = parseInt(urlMatch[1]);
      }
    } catch (error) {
      console.warn("⚠️ URL解析失败:", error);
    }
  }

  if (id && id > 0) {
    courseId.value = id;
    loadInitialData();
  } else {
    uni.showModal({
      title: "错误",
      content: "缺少课程ID参数，请返回重试",
      showCancel: false,
      success: () => {
        uni.navigateBack({
          fail: () => {
            uni.reLaunch({ url: "/pages/student/courses/index" });
          },
        });
      },
    });
  }
});

const loadInitialData = async () => {
  loading.value = true;
  try {
    await Promise.all([loadCourseDetail(), loadSchedules(), loadMyBookings()]);
  } finally {
    loading.value = false;
  }
};

const handleRefresh = async () => {
  refreshing.value = true;
  try {
    await Promise.all([loadCourseDetail(), loadSchedules(), loadMyBookings()]);
  } finally {
    refreshing.value = false;
  }
};

const loadCourseDetail = async () => {
  try {
    const result = await courseApi.get(courseId.value);
    if (isUnmounted) return;
    if (result.code === 0 || result.code === 200) {
      course.value = result.data || {};
    }
  } catch (error) {
    console.error("❌ 加载课程详情失败:", error);
  }
};

const loadSchedules = async () => {
  try {
    const result = await scheduleApi.list({
      course_id: courseId.value,
      status: 1,
    });

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

    schedules.value = finalList;
  } catch (error) {
    console.error("❌ loadSchedules失败:", error);
    schedules.value = [];
  }
};

const loadMyBookings = async () => {
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

    myBookings.value = finalList;
  } catch (error) {
    console.error("❌ 加载预约失败:", error);
  }
};

const handleBooking = async (
  scheduleId: number,
  alreadyBooked: boolean = false,
) => {
  if (alreadyBooked) {
    uni.showModal({
      title: "取消预约",
      content: "确定要取消此预约吗？",
      confirmColor: "#e53935",
      success: async (res) => {
        if (res.confirm) {
          await cancelBooking(scheduleId);
        }
      },
    });
    return;
  }

  uni.showModal({
    title: "确认预约",
    content: "确定要预约此课程吗？",
    confirmColor: "#b8956a",
    success: async (res) => {
      if (res.confirm) {
        await createBooking(scheduleId);
      }
    },
  });
};

const handleQuickBook = () => {
  uni.navigateTo({
    url: `/pages/student/schedule/index?courseId=${courseId.value}`,
  });
};

const createBooking = async (scheduleId: number) => {
  bookingLoading[scheduleId] = true;
  try {
    const result = await bookingApi.create({ schedule_id: scheduleId });
    if (result.code === 0 || result.code === 200) {
      uni.showToast({ title: "✨ 预约成功", icon: "success", duration: 2000 });
      await Promise.all([loadSchedules(), loadMyBookings()]);
    } else {
      uni.showToast({ title: result.msg || "预约失败", icon: "none" });
    }
  } catch (error: any) {
    uni.showToast({ title: error.msg || "预约失败", icon: "none" });
  } finally {
    bookingLoading[scheduleId] = false;
  }
};

const cancelBooking = async (scheduleId: number) => {
  bookingLoading[scheduleId] = true;
  try {
    const booking = myBookings.value.find((b) => b.schedule_id === scheduleId);
    if (!booking) {
      uni.showToast({ title: "未找到预约记录", icon: "none" });
      return;
    }

    if (booking.start_at) {
      const startTime = new Date(booking.start_at).getTime();
      const now = Date.now();
      const minutesBefore = (startTime - now) / (1000 * 60);
      if (minutesBefore <= 90) {
        uni.showToast({ title: "开课前90分钟内不可取消", icon: "none" });
        return;
      }
    }

    const result = await bookingApi.cancel(booking.id);
    if (result.code === 0 || result.code === 200) {
      uni.showToast({ title: "已取消预约", icon: "success", duration: 2000 });
      await Promise.all([loadSchedules(), loadMyBookings()]);
    } else {
      uni.showToast({ title: result.msg || "取消失败", icon: "none" });
    }
  } catch (error: any) {
    uni.showToast({ title: error.msg || "取消失败", icon: "none" });
  } finally {
    bookingLoading[scheduleId] = false;
  }
};
</script>

<style lang="scss">
$bg-primary: #faf7f2;
$bg-card: #ffffff;
$gold-primary: #b8956a;
$gold-light: #d4b896;
$gold-dark: #8b7355;
$text-primary: #2c2416;
$text-secondary: #6b5d4f;
$text-tertiary: #a89b8c;
$border-light: #f0ebe3;
$border-subtle: #e8e0d5;
$success-color: #5a9e6f;
$success-bg: #e8f5e9;
$error-color: #e53935;
$error-bg: #ffebee;
$primary-bg: #f5f0e8;
$space-xs: 8rpx;
$space-sm: 16rpx;
$space-md: 24rpx;
$space-lg: 32rpx;
$space-xl: 40rpx;
$radius-sm: 8rpx;
$radius-md: 12rpx;
$radius-lg: 16rpx;
$radius-xl: 24rpx;
$font-size-caption: 22rpx;
$font-size-body: 28rpx;
$font-size-body_sm: 24rpx;
$font-size-h2: 40rpx;
$font-size-h3: 32rpx;
$font-size-h4: 30rpx;
$font-weight-normal: 400;
$font-weight-medium: 500;
$font-weight-semibold: 600;
$font-weight-bold: 700;

@mixin page-container($bg) {
  min-height: 100vh;
  background: $bg;
}

@mixin main-content {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

@mixin font-style($size, $weight, $line-height: 1.5) {
  font-size: $size;
  font-weight: $weight;
  line-height: $line-height;
}

.course-detail-page {
  @include page-container($bg-primary);
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

/* ========== Hero 封面区域 ========== */
.hero-section {
  position: relative;
  height: 380rpx;
  flex-shrink: 0;
  overflow: hidden;
}

.hero-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.hero-placeholder {
  width: 100%;
  height: 100%;
  background: #1a1612;
  position: relative;
  overflow: hidden;
}

.hero-bg-gradient {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(
      ellipse 600rpx 400rpx at 70% 30%,
      rgba(201, 166, 107, 0.18) 0%,
      transparent 60%
    ),
    radial-gradient(
      ellipse 500rpx 350rpx at 30% 70%,
      rgba(217, 167, 176, 0.13) 0%,
      transparent 55%
    ),
    linear-gradient(155deg, #1a1612 0%, #2d2418 35%, #1f1a14 65%, #1a1612 100%);
}

.hero-mesh {
  position: absolute;
  border-radius: 50%;
  filter: blur(60rpx);
  opacity: 0.5;

  &.mesh-1 {
    top: -20%;
    right: -10%;
    width: 500rpx;
    height: 500rpx;
    background: radial-gradient(
      circle at 40% 40%,
      rgba(201, 166, 107, 0.3),
      rgba(201, 166, 107, 0.05)
    );
  }

  &.mesh-2 {
    bottom: -15%;
    left: -15%;
    width: 450rpx;
    height: 450rpx;
    background: radial-gradient(
      circle at 60% 60%,
      rgba(217, 167, 176, 0.25),
      rgba(217, 167, 176, 0.04)
    );
  }

  &.mesh-3 {
    top: 40%;
    left: 50%;
    width: 300rpx;
    height: 300rpx;
    background: radial-gradient(
      circle at 50% 50%,
      rgba(232, 213, 183, 0.2),
      transparent
    );
    transform: translate(-50%, -50%);
  }
}

.hero-accent-shape {
  position: absolute;
  top: 15%;
  right: 8%;
  width: 180rpx;
  height: 180rpx;
  border: 2rpx solid rgba(201, 166, 107, 0.3);
  border-radius: 50%;
  opacity: 0.7;
}

.hero-gold-line {
  position: absolute;
  top: 28%;
  right: 14%;
  width: 120rpx;
  height: 2rpx;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(201, 166, 107, 0.5),
    transparent
  );
  transform: rotate(-20deg);
}

.hero-brand-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) rotate(-8deg);
  font-size: 120rpx;
  font-weight: 900;
  color: rgba(201, 166, 107, 0.08);
  letter-spacing: 20rpx;
  white-space: nowrap;
  pointer-events: none;
  text-transform: uppercase;
}

.hero-dot-grid {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(
    rgba(201, 166, 107, 0.06) 1rpx,
    transparent 1rpx
  );
  background-size: 28rpx 28rpx;
  opacity: 0.5;
}

.hero-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(
    180deg,
    rgba(26, 26, 26, 0.02) 0%,
    rgba(26, 26, 26, 0.15) 40%,
    rgba(26, 26, 26, 0.5) 70%,
    rgba(26, 26, 26, 0.7) 100%
  );
}

/* ========== 主内容区域 ========== */
.scroll-wrapper {
  @include main-content;
}

.details-content {
  flex: 1;
  padding: 0 24rpx;
  padding-bottom: calc(120rpx + env(safe-area-inset-bottom));
  box-sizing: border-box;
}

/* ========== 课程信息统计栏 ========== */
.info-bar {
  display: flex;
  align-items: center;
  justify-content: space-around;
  background: $bg-card;
  border-radius: $radius-lg;
  padding: 28rpx 24rpx;
  margin-top: 24rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.06);
  position: relative;
  z-index: 1;
}

.info-bar-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8rpx;
}

.info-bar-value {
  font-size: 48rpx;
  font-weight: 700;
  color: $gold-primary;
  line-height: 1;
}

.info-bar-sub {
  display: flex;
  align-items: center;
  gap: 6rpx;
}

.info-bar-sub-icon {
  width: 28rpx;
  height: 28rpx;
}

.info-bar-top {
  display: flex;
  align-items: center;
  gap: 6rpx;
}

.info-bar-top-icon {
  width: 32rpx;
  height: 32rpx;
}

.info-bar-value-sm {
  font-size: 28rpx;
  font-weight: 600;
  color: $gold-primary;
}

.info-bar-label {
  font-size: 22rpx;
  color: $text-tertiary;
}

.info-bar-divider {
  width: 1rpx;
  height: 60rpx;
  background: $border-light;
}

/* ========== 内容卡片 ========== */
.content-card {
  background: $bg-card;
  border-radius: $radius-lg;
  padding: 28rpx 24rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.04);
}

.card-section-header {
  margin-bottom: 20rpx;
}

.section-icon-title {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.section-icon-img {
  width: 44rpx;
  height: 44rpx;
  flex-shrink: 0;
}

.section-title {
  font-size: 32rpx;
  font-weight: 600;
  color: $text-primary;
}

.section-line {
  width: 60rpx;
  height: 4rpx;
  background: linear-gradient(90deg, $gold-light, transparent);
  margin-left: 16rpx;
  border-radius: 2rpx;
  flex-shrink: 0;
}

.card-section-body {
  padding-top: 4rpx;
}

/* ========== 课程简介 ========== */
.description-text {
  font-size: 28rpx;
  font-weight: 400;
  color: $text-secondary;
  line-height: 1.8;
}

/* ========== 上课须知 ========== */
.notice-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.notice-item {
  display: flex;
  align-items: flex-start;
  gap: 12rpx;
}

.notice-dot {
  font-size: 28rpx;
  color: $gold-primary;
  line-height: 1.6;
  flex-shrink: 0;
}

.notice-text {
  font-size: 26rpx;
  color: $text-secondary;
  line-height: 1.7;
}

/* ========== 排期区域 ========== */
.schedule-count {
  display: flex;
  align-items: center;
}

.count-text {
  font-size: 24rpx;
  color: $text-tertiary;
  background: $primary-bg;
  padding: 6rpx 16rpx;
  border-radius: 20rpx;
}

.schedule-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

/* ========== 排期卡片 ========== */
.schedule-card {
  display: flex;
  flex-direction: column;
  background: $bg-primary;
  border-radius: $radius-md;
  border: 1rpx solid $border-subtle;
  padding: 20rpx 24rpx;
  animation: cardFadeIn 0.35s cubic-bezier(0.22, 0.61, 0.36, 1) both;
}

.card-row {
  display: flex;
  align-items: center;
  justify-content: space-between;

  & + & {
    margin-top: 12rpx;
  }
}

.card-row--info {
  justify-content: flex-start;
}

.card-row--action {
  justify-content: space-between;
}

.date-time-group {
  display: flex;
  align-items: baseline;
  flex: 1;
  min-width: 0;
}

.date-text {
  font-size: 28rpx;
  font-weight: 600;
  color: $text-primary;
  flex-shrink: 0;
}

.dot-sep {
  margin: 0 8rpx;
  color: $text-tertiary;
  font-weight: 700;
}

.time-text {
  font-size: 28rpx;
  font-weight: 500;
  color: $gold-primary;
}

.status-tag {
  padding: 4rpx 16rpx;
  border-radius: 20rpx;
  font-size: 22rpx;
  font-weight: 500;
  flex-shrink: 0;
  margin-left: 12rpx;

  &.booked {
    background: $primary-bg;
    color: $gold-primary;
  }

  &.full {
    background: $error-bg;
    color: $error-color;
  }

  &.available {
    background: $success-bg;
    color: $success-color;
  }
}

.info-text {
  font-size: 24rpx;
  color: $text-secondary;
  white-space: nowrap;
}

.info-icon {
  margin-right: 4rpx;
}

.info-divider {
  margin: 0 12rpx;
  color: $text-tertiary;
  font-weight: 700;
}

.capacity-group {
  display: flex;
  align-items: center;
  gap: 12rpx;
  flex: 1;
  min-width: 0;
}

.capacity-bar {
  width: 140rpx;
  height: 8rpx;
  background: $border-light;
  border-radius: 20rpx;
  overflow: hidden;
  flex-shrink: 0;
}

.capacity-fill {
  height: 100%;
  background: $gold-primary;
  border-radius: 20rpx;
  transition: width 0.3s ease;

  &.full {
    background: $error-color;
  }
}

.capacity-label {
  font-size: 22rpx;
  color: $text-tertiary;
  flex-shrink: 0;
}

.book-btn {
  padding: 8rpx 28rpx;
  border-radius: 30rpx;
  font-size: 24rpx;
  font-weight: 600;
  background: linear-gradient(135deg, $gold-primary, $gold-dark);
  color: #fff;
  border: none;
  line-height: 1.5;
  flex-shrink: 0;
  margin-left: auto;

  &:active {
    transform: scale(0.95);
  }

  &.disabled {
    background: $border-light;
    color: $text-tertiary;
  }

  &.booked {
    background: $error-bg;
    color: $error-color;
  }
}

/* ========== 底部预约按钮 ========== */
.footer-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 20rpx 32rpx;
  padding-bottom: calc(20rpx + env(safe-area-inset-bottom));
  background: linear-gradient(
    180deg,
    rgba(250, 247, 242, 0) 0%,
    rgba(250, 247, 242, 0.95) 30%,
    $bg-primary 100%
  );
  z-index: 10;
}

.footer-book-btn {
  width: 100%;
  height: 88rpx;
  background: linear-gradient(135deg, #d4b896 0%, #c9a66b 100%);
  border-radius: 44rpx;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8rpx 24rpx rgba(201, 166, 107, 0.35);

  &::after {
    border: none;
  }

  &:active {
    transform: scale(0.98);
    box-shadow: 0 4rpx 16rpx rgba(201, 166, 107, 0.25);
  }
}

.footer-btn-text {
  font-size: 32rpx;
  font-weight: 600;
  color: #ffffff;
  letter-spacing: 4rpx;
}

/* ========== 底部安全距离 ========== */
.bottom-spacer {
  height: 120rpx;
}

/* ========== 加载遮罩 ========== */
.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(250, 247, 242, 0.95);
  backdrop-filter: blur(10px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
}

/* ========== 动画 ========== */
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
