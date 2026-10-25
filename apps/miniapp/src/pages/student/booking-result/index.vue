<template>
  <view class="booking-result-page">
    <!-- 加载态：参数解析 / 卡余额拉取中 -->
    <view v-if="loading" class="result-state">
      <text class="state-text">加载中...</text>
    </view>

    <!-- 失败态：按 statusCode + 后端 msg 分类给建议（不回显内部信息） -->
    <view v-else-if="isFail" class="result-state">
      <view class="state-icon">
        <AppIcon name="warning" :size="96" color="#c97a5e" />
      </view>
      <text class="state-title">预约失败</text>
      <text class="state-desc">{{ failMessage }}</text>
      <view class="suggest-card">
        <text class="suggest-label">建议</text>
        <text class="suggest-text">{{ failSuggest }}</text>
      </view>
      <view class="state-actions">
        <view class="action-btn primary" @tap="handleBackToRechoose">
          <text class="action-text primary-text">返回重选</text>
        </view>
        <view class="action-btn secondary" @tap="goBookings">
          <text class="action-text secondary-text">查看我的预约</text>
        </view>
      </view>
    </view>

    <!-- 成功态 -->
    <template v-else>
      <view class="result-hero">
        <view class="hero-icon">
          <AppIcon name="check-circle" :size="96" color="#fff" />
        </view>
        <text class="hero-title">{{ successTitle }}</text>
        <text class="hero-subtitle">{{ successSubtitle }}</text>
      </view>

      <!-- 排期摘要 -->
      <view class="info-card">
        <view class="section-head">
          <text class="section-title">排期信息</text>
          <view class="section-line"></view>
        </view>
        <view class="info-row">
          <AppIcon name="book" :size="28" color="#b8956a" />
          <text class="info-text">{{ courseName || "未知课程" }}</text>
        </view>
        <view class="info-row">
          <AppIcon name="calendar" :size="28" color="#b8956a" />
          <text class="info-text">{{ formatDate(startAt) }}</text>
        </view>
        <view class="info-row">
          <AppIcon name="clock" :size="28" color="#b8956a" />
          <text class="info-text"
            >{{ formatTime(startAt) }} - {{ formatTime(endAt) }}</text
          >
        </view>
        <view class="info-row">
          <AppIcon name="user" :size="28" color="#b8956a" />
          <text class="info-text">{{ teacherName || "未知教师" }}</text>
        </view>
        <view class="info-row">
          <AppIcon name="location" :size="28" color="#b8956a" />
          <text class="info-text">{{ classroomName || "未安排教室" }}</text>
        </view>
      </view>

      <!-- 扣次反馈 -->
      <view class="info-card">
        <view class="section-head">
          <text class="section-title">扣次信息</text>
          <view class="section-line"></view>
        </view>
        <view class="deduct-row">
          <text class="deduct-text">{{ deductText }}</text>
        </view>
      </view>

      <!-- 出口 -->
      <view class="bottom-actions">
        <view class="action-btn primary" @tap="goBookings">
          <text class="action-text primary-text">查看我的预约</text>
        </view>
        <view class="action-btn secondary" @tap="goHome">
          <text class="action-text secondary-text">返回首页</text>
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

// ===== 页面参数（来自 booking-confirm redirectTo） =====
const loading = ref(true);
const isFail = ref(false);

const scheduleId = ref(0);
const cardId = ref(0);
// 卡类型：取自 booking-confirm 已选卡（用户真实选择），剩余次数由卡详情接口拉取（后端权威）
const cardType = ref("");
const remainingCredits = ref<number | null>(null);

const courseName = ref("");
const startAt = ref("");
const endAt = ref("");
const teacherName = ref("");
const classroomName = ref("");

const failMessage = ref("预约失败，请稍后重试");
const failStatusCode = ref<number | null>(null);

function safeDecode(value?: string): string {
  if (!value) return "";
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

// ===== 失败分类：409 / msg 关键词 → 建议动作 =====
type FailKind = "full" | "conflict" | "balance" | "card" | "generic";

const failKind = computed<FailKind>(() => {
  const msg = failMessage.value || "";
  const code = failStatusCode.value;
  if (code === 409 || /约满|名额|已满/.test(msg)) return "full";
  if (/重叠|冲突/.test(msg)) return "conflict";
  if (/余额|次数不足|课时不足|不足/.test(msg)) return "balance";
  if (/卡/.test(msg)) return "card";
  return "generic";
});

const failSuggest = computed(() => {
  switch (failKind.value) {
    case "full":
      return "该排期名额已满，请选择其他时间段的排期";
    case "conflict":
      return "该时间段与您已有的预约重叠，请选择其他排期";
    case "balance":
      return "当前会员卡余额不足，请返回更换其他会员卡重试";
    case "card":
      return "当前会员卡不可用，请返回更换其他会员卡重试";
    default:
      return "请稍后重试；如多次失败，请联系机构前台处理";
  }
});

// ===== 成功态文案（按卡类型） =====
const successTitle = computed(() => {
  if (cardType.value === "count") return "预约成功 · 已预扣 1 次";
  if (cardType.value === "period") return "预约成功 · 首次上课后激活";
  return "预约成功";
});

const successSubtitle = computed(() => {
  if (cardType.value === "count") return "排期完成后确认扣次，取消将回补";
  if (cardType.value === "period") return "期卡在首次上课完成后激活并写入有效期";
  return "";
});

const deductText = computed(() => {
  if (cardType.value === "count") {
    if (remainingCredits.value !== null) {
      return `已预扣 1 次 · 剩余 ${remainingCredits.value} 次`;
    }
    return "已预扣 1 次";
  }
  if (cardType.value === "period") return "期卡不扣次，首次上课后激活";
  if (cardType.value === "unlimited") return "不限次卡，不涉及扣次";
  return "本次预约不涉及次数扣减";
});

// ===== 格式化 =====
const formatDate = (dateStr: string) => {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return "";
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const weekDays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  const weekDay = weekDays[date.getDay()];
  return `${month}-${day} ${weekDay}`;
};

const formatTime = (dateStr: string) => {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return "";
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${hours}:${minutes}`;
};

// ===== 拉取次卡剩余次数（后端权威：预约事务提交后的真实余额） =====
const loadRemainingCredits = async () => {
  if (cardType.value !== "count" || !cardId.value) return;
  try {
    const res = await membershipApi.getCardDetail(cardId.value);
    const data: any = res?.data;
    if (data && typeof data.remaining_credits === "number") {
      remainingCredits.value = data.remaining_credits;
    }
  } catch (e) {
    // 拉取失败降级为不展示剩余次数（扣次反馈仍展示「已预扣 1 次」）
    console.warn("加载卡剩余次数失败:", e);
  }
};

// ===== 出口 =====
const goBookings = () => {
  uni.redirectTo({ url: "/pages/student/bookings/index" });
};

const goHome = () => {
  uni.reLaunch({ url: "/pages/index/index" });
};

const handleBackToRechoose = () => {
  const pages = getCurrentPages();
  if (pages.length > 1) {
    uni.navigateBack();
  } else {
    uni.reLaunch({ url: "/pages/index/index" });
  }
};

onLoad((options) => {
  if (!checkLogin("student")) return;

  const result = options?.result;

  // 失败态入口：仅展示分类与建议，无任何写操作
  if (result === "fail") {
    const msg = safeDecode(options?.msg);
    if (msg) failMessage.value = msg;
    const code = Number(options?.code);
    failStatusCode.value = Number.isNaN(code) || !code ? null : code;
    isFail.value = true;
    loading.value = false;
    return;
  }

  // 成功态：必须有排期参数，否则兜底为失败态（参数缺失）
  scheduleId.value = Number(options?.schedule_id) || 0;
  if (result !== "success" || !scheduleId.value) {
    failMessage.value = "结果信息缺失，请在「我的预约」中查看预约状态";
    isFail.value = true;
    loading.value = false;
    return;
  }

  cardId.value = Number(options?.card_id) || 0;
  cardType.value = safeDecode(options?.card_type);
  courseName.value = safeDecode(options?.course_name);
  startAt.value = safeDecode(options?.start_at);
  endAt.value = safeDecode(options?.end_at);
  teacherName.value = safeDecode(options?.teacher_name);
  classroomName.value = safeDecode(options?.classroom_name);

  loadRemainingCredits().finally(() => {
    loading.value = false;
  });
});
</script>

<style lang="scss">
@import "@/styles/theme/_variables.scss";
@import "@/styles/theme/_mixins.scss";

.booking-result-page {
  // 不使用 page-container：其 overflow:hidden + 100vh 会阻止页面原生滚动
  width: 100%;
  min-height: 100vh;
  background: linear-gradient(180deg, #faf6f0 0%, #f5ede3 100%);
  padding: $space-md;
  padding-bottom: 60rpx;
  box-sizing: border-box;
}

// ===== 状态块（loading / 失败） =====
.result-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 120rpx $space-md;
  gap: $space-sm;
}

.state-icon {
  margin-bottom: $space-sm;
}

.state-text {
  font-size: $font-size-body;
  color: $text-tertiary;
}

.state-title {
  font-size: 36rpx;
  font-weight: $font-weight-semibold;
  color: $text-secondary;
}

.state-desc {
  font-size: $font-size-body;
  color: $text-secondary;
  text-align: center;
  line-height: 1.6;
}

.suggest-card {
  width: 100%;
  margin-top: $space-sm;
  padding: $space-md;
  background: #fff;
  border-radius: $radius-lg;
  border: 1rpx solid rgba(201, 166, 107, 0.15);
  box-shadow: 0 4rpx 20rpx rgba(201, 166, 107, 0.08);
  display: flex;
  flex-direction: column;
  gap: 12rpx;
  box-sizing: border-box;
}

.suggest-label {
  font-size: $font-size-body-sm;
  font-weight: $font-weight-semibold;
  color: #b8956a;
}

.suggest-text {
  font-size: $font-size-body;
  color: $text-secondary;
  line-height: 1.6;
}

// ===== 成功态 =====
.result-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 64rpx $space-md 48rpx;
  gap: 16rpx;
}

.hero-icon {
  width: 128rpx;
  height: 128rpx;
  border-radius: 50%;
  background: linear-gradient(135deg, #d4b896 0%, #c9a66b 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8rpx 24rpx rgba(201, 166, 107, 0.35);
  margin-bottom: 8rpx;
}

.hero-title {
  font-size: 36rpx;
  font-weight: $font-weight-semibold;
  color: #5a4a3a;
  text-align: center;
}

.hero-subtitle {
  font-size: $font-size-body-sm;
  color: #8a7a6a;
  text-align: center;
}

// ===== 信息卡片 =====
.info-card {
  background: #fff;
  border-radius: $radius-lg;
  margin-bottom: $space-md;
  box-shadow: 0 4rpx 20rpx rgba(201, 166, 107, 0.08);
  padding: 24rpx 28rpx;
}

.section-head {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 20rpx;
}

.section-title {
  font-size: 30rpx;
  font-weight: $font-weight-semibold;
  color: #5a4a3a;
}

.section-line {
  flex: 1;
  height: 2rpx;
  background: linear-gradient(90deg, rgba(201, 166, 107, 0.4), transparent);
}

.info-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 16rpx;

  &:last-child {
    margin-bottom: 0;
  }
}

.info-text {
  font-size: 26rpx;
  color: #8a7a6a;
}

.deduct-row {
  padding: 8rpx 0;
}

.deduct-text {
  font-size: 28rpx;
  font-weight: $font-weight-medium;
  color: #b8956a;
}

// ===== 按钮 =====
.state-actions {
  width: 100%;
  margin-top: $space-md;
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.bottom-actions {
  margin-top: $space-lg;
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.action-btn {
  width: 100%;
  height: 88rpx;
  border-radius: 44rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;

  &:active {
    transform: scale(0.97);
    opacity: 0.9;
  }

  &.primary {
    background: linear-gradient(135deg, #d4b896 0%, #c9a66b 100%);
    box-shadow: 0 4rpx 16rpx rgba(201, 166, 107, 0.3);
  }

  &.secondary {
    background: #fff;
    border: 1rpx solid rgba(201, 166, 107, 0.3);
  }
}

.action-text {
  font-size: $font-size-body;
  font-weight: $font-weight-medium;

  &.primary-text {
    color: #fff;
  }

  &.secondary-text {
    color: #b8956a;
  }
}
</style>
