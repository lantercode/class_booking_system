<template>
  <view class="membership_container">
    <!-- 顶部筛选标签（固定） -->
    <view class="filter-tabs">
      <view
        class="filter-tab"
        :class="{ 'tab-active': selectedTab === 'valid' }"
        @tap="selectedTab = 'valid'"
      >
        <text class="tab-text">有效课卡 {{ validCards.length }}</text>
      </view>
      <view
        class="filter-tab"
        :class="{ 'tab-active': selectedTab === 'invalid' }"
        @tap="selectedTab = 'invalid'"
      >
        <text class="tab-text">无效课卡 {{ invalidCards.length }}</text>
      </view>
    </view>

    <!-- 可滚动区域：会员卡列表 -->
    <scroll-view scroll-y class="cards-scroll" :show-scrollbar="false">
      <!-- 有效卡列表 -->
      <view v-if="selectedTab === 'valid'" class="cards-section">
        <!-- 空状态 -->
        <view v-if="validCards.length === 0" class="empty-state">
          <view class="empty-card-illustration">
            <view class="card-3d">
              <view class="card-face">
                <AppIcon name="crown" :size="48" color="#c9a66b" />
              </view>
              <view class="card-shadow"></view>
            </view>
            <view class="sparkles">
              <view class="sparkle sparkle-1">✦</view>
              <view class="sparkle sparkle-2">✦</view>
              <view class="sparkle sparkle-3"></view>
            </view>
          </view>
          <text class="empty-title">暂无有效会员卡</text>
          <text class="empty-desc">您还没有领取或激活会员卡</text>
          <button class="go-handle-btn" @tap="goToHandle">
            <AppIcon name="card" :size="32" color="#fff" />
            <text>前往办理</text>
            <text class="btn-arrow">›</text>
          </button>

          <!-- 会员卡权益 -->
          <view class="benefits-section">
            <text class="benefits-title">会员卡可以为您带来</text>
            <view class="benefits-grid">
              <view class="benefit-item">
                <AppIcon name="crown" :size="48" color="#c9a66b" />
                <text class="benefit-text">专属课程优惠</text>
              </view>
              <view class="benefit-item">
                <AppIcon name="tag" :size="48" color="#c9a66b" />
                <text class="benefit-text">更多会员权益</text>
              </view>
              <view class="benefit-item">
                <AppIcon name="calendar-check" :size="48" color="#c9a66b" />
                <text class="benefit-text">优先预约课程</text>
              </view>
              <view class="benefit-item">
                <AppIcon name="heart" :size="48" color="#c9a66b" />
                <text class="benefit-text">享受专属服务</text>
              </view>
            </view>
          </view>
        </view>
        <template v-else>
          <!-- 使用中的卡（金色渐变背景） -->
          <view
            v-for="card in activeCards"
            :key="card.id"
            class="card-item card-active"
          >
            <view class="card-content">
              <!-- 中间内容 -->
              <view class="card-main">
                <!-- 头部 -->
                <view class="card-header">
                  <text class="card-name">{{
                    card.product_name || "会员卡"
                  }}</text>
                  <view class="card-status-badge status-active">
                    <view class="badge-dot"></view>
                    <text class="badge-text">使用中</text>
                  </view>
                </view>

                <!-- 卡号 -->
                <view class="card-no-row">
                  <text class="card-no-label">卡号</text>
                  <text class="card-no-text">{{ card.card_no || "-" }}</text>
                  <view
                    class="copy-icon-btn"
                    @tap.stop="copyCardNo(card.card_no)"
                  >
                    <AppIcon
                      name="copy"
                      :size="28"
                      color="rgba(90, 74, 42, 0.5)"
                    />
                  </view>
                </view>

                <!-- 次卡：剩余次数 / 总次数 + 有效期 -->
                <view v-if="card.card_type === 'count'" class="card-usage">
                  <view class="usage-main">
                    <view class="credits-display">
                      <text class="credits-remaining">{{
                        card.remaining_credits ?? 0
                      }}</text>
                      <text class="credits-separator">/</text>
                      <text class="credits-total">{{
                        card.total_credits ?? 0
                      }}</text>
                      <text class="credits-unit">次</text>
                    </view>
                    <view class="usage-divider-line"></view>
                    <text class="usage-valid-range"
                      >有效期至 {{ formatDateShort(card.expire_at) }}</text
                    >
                  </view>
                </view>

                <!-- 期卡：剩余天数 + 有效期 -->
                <view v-if="card.card_type === 'period'" class="card-usage">
                  <view class="usage-main">
                    <view class="credits-display">
                      <text class="credits-label">剩余</text>
                      <text class="credits-remaining">{{
                        getValidDays(card)
                      }}</text>
                      <text class="credits-unit">天</text>
                    </view>
                    <view class="usage-divider-line"></view>
                    <text class="usage-valid-range"
                      >有效期至 {{ formatDateShort(card.expire_at) }}</text
                    >
                  </view>
                </view>

                <!-- 无限卡 -->
                <view v-if="card.card_type === 'unlimited'" class="card-usage">
                  <view class="usage-main">
                    <AppIcon
                      name="infinity"
                      :size="32"
                      color="rgba(90, 74, 42, 0.6)"
                    />
                    <text class="usage-unlimited-text">不限次</text>
                    <view class="usage-divider-line"></view>
                    <text class="usage-valid-range"
                      >有效期至 {{ formatDateShort(card.expire_at) }}</text
                    >
                  </view>
                </view>
              </view>
            </view>
          </view>

          <!-- 已用完的卡（白色背景） -->
          <view
            v-for="card in usedUpCards"
            :key="card.id"
            class="card-item card-used-up"
          >
            <view class="card-content">
              <!-- 中间内容 -->
              <view class="card-main">
                <!-- 头部 -->
                <view class="card-header">
                  <text class="card-name">{{
                    card.product_name || "会员卡"
                  }}</text>
                  <view class="card-status-badge status-used-up">
                    <view class="badge-dot"></view>
                    <text class="badge-text">已用完</text>
                  </view>
                </view>

                <!-- 卡号 -->
                <view class="card-no-row">
                  <text class="card-no-label">卡号</text>
                  <text class="card-no-text">{{ card.card_no || "-" }}</text>
                  <view
                    class="copy-icon-btn"
                    @tap.stop="copyCardNo(card.card_no)"
                  >
                    <AppIcon
                      name="copy"
                      :size="28"
                      color="rgba(158, 158, 158, 0.5)"
                    />
                  </view>
                </view>

                <!-- 次卡：剩余次数 / 总次数 + 有效期 -->
                <view v-if="card.card_type === 'count'" class="card-usage">
                  <view class="usage-main">
                    <view class="credits-display">
                      <text class="credits-remaining usage-value-zero">0</text>
                      <text class="credits-separator">/</text>
                      <text class="credits-total">{{
                        card.total_credits ?? 0
                      }}</text>
                      <text class="credits-unit">次</text>
                    </view>
                    <view class="usage-divider-line"></view>
                    <text class="usage-valid-range"
                      >有效期至 {{ formatDateShort(card.expire_at) }}</text
                    >
                  </view>
                </view>

                <!-- 期卡：剩余天数 + 有效期 -->
                <view v-if="card.card_type === 'period'" class="card-usage">
                  <view class="usage-main">
                    <view class="credits-display">
                      <text class="credits-label">剩余</text>
                      <text class="credits-remaining usage-value-zero">0</text>
                      <text class="credits-unit">天</text>
                    </view>
                    <view class="usage-divider-line"></view>
                    <text class="usage-valid-range"
                      >有效期至 {{ formatDateShort(card.expire_at) }}</text
                    >
                  </view>
                </view>

                <!-- 无限卡 -->
                <view v-if="card.card_type === 'unlimited'" class="card-usage">
                  <view class="usage-main">
                    <AppIcon
                      name="infinity"
                      :size="32"
                      color="rgba(158, 158, 158, 0.5)"
                    />
                    <text class="usage-unlimited-text">不限次</text>
                    <view class="usage-divider-line"></view>
                    <text class="usage-valid-range"
                      >有效期至 {{ formatDateShort(card.expire_at) }}</text
                    >
                  </view>
                </view>
              </view>
            </view>
          </view>

          <!-- 未激活的卡（白色背景） -->
          <view
            v-for="card in pendingCards"
            :key="card.id"
            class="card-item card-pending"
          >
            <view class="card-content">
              <!-- 中间内容 -->
              <view class="card-main">
                <!-- 头部 -->
                <view class="card-header">
                  <text class="card-name">{{
                    card.product_name || "会员卡"
                  }}</text>
                  <view class="card-status-badge status-pending">
                    <view class="badge-dot"></view>
                    <text class="badge-text">未激活</text>
                  </view>
                </view>

                <!-- 卡号 -->
                <view class="card-no-row">
                  <text class="card-no-label">卡号</text>
                  <text class="card-no-text">{{ card.card_no || "-" }}</text>
                  <view
                    class="copy-icon-btn"
                    @tap.stop="copyCardNo(card.card_no)"
                  >
                    <AppIcon
                      name="copy"
                      :size="28"
                      color="rgba(158, 158, 158, 0.5)"
                    />
                  </view>
                </view>

                <!-- 可激活的卡：使用信息 + 立即激活按钮同行 -->
                <view
                  v-if="!getActivationBlockReason(card)"
                  class="usage-with-activate"
                >
                  <!-- 无限卡：显示不限次 + 有效期 -->
                  <view
                    v-if="card.card_type === 'unlimited'"
                    class="card-usage usage-inline"
                  >
                    <view class="usage-main">
                      <AppIcon
                        name="infinity"
                        :size="32"
                        color="rgba(158, 158, 158, 0.5)"
                      />
                      <text class="usage-unlimited-text">不限次</text>
                      <view class="usage-divider-line"></view>
                      <text class="usage-valid-range"
                        >{{ formatDateShort(card.valid_from) }} ~
                        {{ formatDateShort(card.expire_at) }}</text
                      >
                    </view>
                  </view>

                  <!-- 次卡：剩余次数 / 总次数 + 有效期 -->
                  <view
                    v-if="card.card_type === 'count'"
                    class="card-usage usage-inline"
                  >
                    <view class="usage-main">
                      <view class="credits-display">
                        <text class="credits-remaining">{{
                          card.remaining_credits ?? 0
                        }}</text>
                        <text class="credits-separator">/</text>
                        <text class="credits-total">{{
                          card.total_credits ?? 0
                        }}</text>
                        <text class="credits-unit">次</text>
                      </view>
                      <view class="usage-divider-line"></view>
                      <text class="usage-valid-range"
                        >{{ formatDateShort(card.valid_from) }} ~
                        {{ formatDateShort(card.expire_at) }}</text
                      >
                    </view>
                  </view>

                  <!-- 期卡：剩余天数 + 有效期 -->
                  <view
                    v-if="card.card_type === 'period'"
                    class="card-usage usage-inline"
                  >
                    <view class="usage-main">
                      <view class="credits-display">
                        <text class="credits-label">剩余</text>
                        <text class="credits-remaining">{{
                          getValidDays(card)
                        }}</text>
                        <text class="credits-unit">天</text>
                      </view>
                      <view class="usage-divider-line"></view>
                      <text class="usage-valid-range"
                        >{{ formatDateShort(card.valid_from) }} ~
                        {{ formatDateShort(card.expire_at) }}</text
                      >
                    </view>
                  </view>

                  <!-- 立即激活按钮 -->
                  <view
                    class="activate-btn-inline"
                    @tap.stop="handleActivate(card)"
                  >
                    <text class="activate-btn-text">立即激活</text>
                  </view>
                </view>

                <!-- 无法激活的卡：仅显示使用信息 -->
                <template v-else>
                  <!-- 无限卡 -->
                  <view
                    v-if="card.card_type === 'unlimited'"
                    class="card-usage"
                  >
                    <view class="usage-main">
                      <AppIcon
                        name="infinity"
                        :size="32"
                        color="rgba(158, 158, 158, 0.5)"
                      />
                      <text class="usage-unlimited-text">不限次</text>
                      <view class="usage-divider-line"></view>
                      <text class="usage-valid-range"
                        >{{ formatDateShort(card.valid_from) }} ~
                        {{ formatDateShort(card.expire_at) }}</text
                      >
                    </view>
                  </view>

                  <!-- 次卡：剩余次数 / 总次数 + 有效期 -->
                  <view v-if="card.card_type === 'count'" class="card-usage">
                    <view class="usage-main">
                      <view class="credits-display">
                        <text class="credits-remaining">{{
                          card.remaining_credits ?? 0
                        }}</text>
                        <text class="credits-separator">/</text>
                        <text class="credits-total">{{
                          card.total_credits ?? 0
                        }}</text>
                        <text class="credits-unit">次</text>
                      </view>
                      <view class="usage-divider-line"></view>
                      <text class="usage-valid-range"
                        >{{ formatDateShort(card.valid_from) }} ~
                        {{ formatDateShort(card.expire_at) }}</text
                      >
                    </view>
                  </view>

                  <!-- 期卡：剩余天数 + 有效期 -->
                  <view v-if="card.card_type === 'period'" class="card-usage">
                    <view class="usage-main">
                      <view class="credits-display">
                        <text class="credits-label">剩余</text>
                        <text class="credits-remaining">{{
                          getValidDays(card)
                        }}</text>
                        <text class="credits-unit">天</text>
                      </view>
                      <view class="usage-divider-line"></view>
                      <text class="usage-valid-range"
                        >{{ formatDateShort(card.valid_from) }} ~
                        {{ formatDateShort(card.expire_at) }}</text
                      >
                    </view>
                  </view>
                </template>
              </view>
            </view>

            <!-- 未激活警告框（仅无法激活时显示） -->
            <view
              v-if="getActivationBlockReason(card)"
              class="activation-warning-box"
            >
              <view class="warning-left">
                <AppIcon name="warning" :size="32" color="#c9a66b" />
                <view class="warning-text-content">
                  <text class="warning-title">当前无法激活</text>
                  <text class="warning-desc">{{
                    getActivationBlockReason(card)
                  }}</text>
                </view>
              </view>
            </view>
          </view>

          <!-- 冻结中的卡（白色背景） -->
          <view
            v-for="card in frozenCards"
            :key="card.id"
            class="card-item card-frozen"
          >
            <view class="card-content">
              <!-- 中间内容 -->
              <view class="card-main">
                <!-- 头部 -->
                <view class="card-header">
                  <text class="card-name">{{
                    card.product_name || "会员卡"
                  }}</text>
                  <view class="card-status-badge status-frozen">
                    <view class="badge-dot"></view>
                    <text class="badge-text">冻结中</text>
                  </view>
                </view>

                <!-- 卡号 -->
                <view class="card-no-row">
                  <text class="card-no-label">卡号</text>
                  <text class="card-no-text">{{ card.card_no || "-" }}</text>
                  <view
                    class="copy-icon-btn"
                    @tap.stop="copyCardNo(card.card_no)"
                  >
                    <AppIcon
                      name="copy"
                      :size="28"
                      color="rgba(158, 158, 158, 0.5)"
                    />
                  </view>
                </view>

                <!-- 冻结信息 -->
                <view class="card-usage">
                  <view class="usage-main">
                    <text class="usage-frozen-text">冻结中</text>
                    <view class="usage-divider-line"></view>
                    <text class="usage-frozen-reason">{{
                      card.frozen_reason || "无"
                    }}</text>
                  </view>
                </view>

                <!-- 冻结到期时间 + 提前解冻按钮 -->
                <view v-if="card.frozen_until" class="usage-with-unfreeze">
                  <view class="card-usage">
                    <view class="usage-main">
                      <text class="usage-frozen-until-label">预计解冻</text>
                      <text class="usage-frozen-until">{{
                        formatDateShort(card.frozen_until)
                      }}</text>
                    </view>
                  </view>
                  <!-- 提前解冻按钮 -->
                  <view
                    class="unfreeze-btn-inline"
                    @tap.stop="handleUnfreeze(card)"
                  >
                    <text class="unfreeze-btn-text">提前解冻</text>
                  </view>
                </view>
              </view>
            </view>
          </view>
        </template>
      </view>

      <!-- 无效卡列表（过期卡） -->
      <view v-if="selectedTab === 'invalid'" class="cards-section">
        <!-- 空状态 -->
        <view v-if="invalidCards.length === 0" class="empty-state">
          <view class="empty-card-illustration">
            <view class="card-3d">
              <view class="card-face card-face-invalid">
                <AppIcon name="card-invalid" :size="48" color="#b8a088" />
              </view>
              <view class="card-shadow"></view>
            </view>
          </view>
          <text class="empty-title">暂无无效卡</text>
          <text class="empty-desc">所有会员卡均在有效期内</text>
        </view>
        <template v-else>
          <!-- 已过期的卡 -->
          <view
            v-for="card in expiredCards"
            :key="card.id"
            class="card-item card-expired"
          >
            <view class="card-content">
              <!-- 中间内容 -->
              <view class="card-main">
                <!-- 头部 -->
                <view class="card-header">
                  <text class="card-name">{{
                    card.product_name || "会员卡"
                  }}</text>
                  <view class="card-status-badge status-expired">
                    <view class="badge-dot"></view>
                    <text class="badge-text">已过期</text>
                  </view>
                </view>

                <!-- 卡号 -->
                <view class="card-no-row">
                  <text class="card-no-label">卡号</text>
                  <text class="card-no-text">{{ card.card_no || "-" }}</text>
                  <view
                    class="copy-icon-btn"
                    @tap.stop="copyCardNo(card.card_no)"
                  >
                    <AppIcon
                      name="copy"
                      :size="28"
                      color="rgba(158, 158, 158, 0.5)"
                    />
                  </view>
                </view>

                <!-- 次卡：剩余次数 / 总次数 + 过期时间 -->
                <view v-if="card.card_type === 'count'" class="card-usage">
                  <view class="usage-main usage-main-expired">
                    <view class="credits-display">
                      <text class="credits-remaining usage-value-zero">0</text>
                      <text class="credits-separator">/</text>
                      <text class="credits-total">{{
                        card.total_credits ?? 0
                      }}</text>
                      <text class="credits-unit">次</text>
                    </view>
                    <view class="usage-divider-line"></view>
                    <text class="usage-valid-range"
                      >过期时间 {{ formatDateShort(card.expire_at) }}</text
                    >
                  </view>
                </view>

                <!-- 期卡：剩余天数 + 过期时间 -->
                <view v-if="card.card_type === 'period'" class="card-usage">
                  <view class="usage-main usage-main-expired">
                    <view class="credits-display">
                      <text class="credits-label">剩余</text>
                      <text class="credits-remaining usage-value-zero">0</text>
                      <text class="credits-unit">天</text>
                    </view>
                    <view class="usage-divider-line"></view>
                    <text class="usage-valid-range"
                      >过期时间 {{ formatDateShort(card.expire_at) }}</text
                    >
                  </view>
                </view>

                <!-- 无限卡 -->
                <view v-if="card.card_type === 'unlimited'" class="card-usage">
                  <view class="usage-main">
                    <AppIcon
                      name="infinity"
                      :size="32"
                      color="rgba(158, 158, 158, 0.5)"
                    />
                    <text class="usage-unlimited-text">不限次</text>
                    <view class="usage-divider-line"></view>
                    <text class="usage-valid-range"
                      >过期时间 {{ formatDateShort(card.expire_at) }}</text
                    >
                  </view>
                </view>
              </view>
            </view>
          </view>

          <!-- 已作废的卡 -->
          <view
            v-for="card in voidedCards"
            :key="card.id"
            class="card-item card-voided"
          >
            <view class="card-content">
              <!-- 中间内容 -->
              <view class="card-main">
                <!-- 头部 -->
                <view class="card-header">
                  <text class="card-name">{{
                    card.product_name || "会员卡"
                  }}</text>
                  <view class="card-status-badge status-voided">
                    <view class="badge-dot"></view>
                    <text class="badge-text">已作废</text>
                  </view>
                </view>

                <!-- 卡号 -->
                <view class="card-no-row">
                  <text class="card-no-label">卡号</text>
                  <text class="card-no-text">{{ card.card_no || "-" }}</text>
                  <view
                    class="copy-icon-btn"
                    @tap.stop="copyCardNo(card.card_no)"
                  >
                    <AppIcon
                      name="copy"
                      :size="28"
                      color="rgba(158, 158, 158, 0.5)"
                    />
                  </view>
                </view>

                <!-- 次卡：剩余次数 / 总次数 + 作废时间 -->
                <view v-if="card.card_type === 'count'" class="card-usage">
                  <view class="usage-main usage-main-expired">
                    <view class="credits-display">
                      <text class="credits-remaining usage-value-zero">0</text>
                      <text class="credits-separator">/</text>
                      <text class="credits-total">{{
                        card.total_credits ?? 0
                      }}</text>
                      <text class="credits-unit">次</text>
                    </view>
                    <view class="usage-divider-line"></view>
                    <text class="usage-valid-range"
                      >作废时间 {{ formatDateShort(card.expire_at) }}</text
                    >
                  </view>
                </view>

                <!-- 期卡：剩余天数 + 作废时间 -->
                <view v-if="card.card_type === 'period'" class="card-usage">
                  <view class="usage-main usage-main-expired">
                    <view class="credits-display">
                      <text class="credits-label">剩余</text>
                      <text class="credits-remaining usage-value-zero">0</text>
                      <text class="credits-unit">天</text>
                    </view>
                    <view class="usage-divider-line"></view>
                    <text class="usage-valid-range"
                      >作废时间 {{ formatDateShort(card.expire_at) }}</text
                    >
                  </view>
                </view>

                <!-- 无限卡 -->
                <view v-if="card.card_type === 'unlimited'" class="card-usage">
                  <view class="usage-main">
                    <AppIcon
                      name="infinity"
                      :size="32"
                      color="rgba(158, 158, 158, 0.5)"
                    />
                    <text class="usage-unlimited-text">不限次</text>
                    <view class="usage-divider-line"></view>
                    <text class="usage-valid-range"
                      >作废时间 {{ formatDateShort(card.expire_at) }}</text
                    >
                  </view>
                </view>
              </view>
            </view>
          </view>
        </template>
      </view>
    </scroll-view>
  </view>
</template>

<script setup lang="ts">
import { membershipApi } from "@/api";
import { checkLogin } from "@/utils/auth";
import { computed, onMounted, ref } from "vue";

interface MembershipCard {
  id: number;
  card_no?: string;
  card_type?: string;
  product_name?: string;
  total_credits?: number;
  used_credits: number;
  remaining_credits: number | null;
  status: number;
  expire_at: string | null;
  valid_from: string | null;
  frozen_at: string | null;
  frozen_until: string | null;
  frozen_reason: string | null;
  applicable_course_type_code?: string;
}

const cards = ref<MembershipCard[]>([]);
const loading = ref(true);
const selectedTab = ref("valid");

// 使用中的卡列表（status === 1）
// 次卡：remaining_credits > 0
// 期卡/无限卡：只看 status === 1
const activeCards = computed(() => {
  return cards.value.filter((c) => {
    if (c.status !== 1) return false;
    // 次卡需要检查剩余次数
    if (c.card_type === "count") {
      return (c.remaining_credits ?? 0) > 0;
    }
    // 期卡/无限卡只看状态
    return true;
  });
});

// 已用完的卡（仅次卡，status === 1 但 remaining_credits === 0）
// 期卡不会"用完"，只会"过期"
const usedUpCards = computed(() => {
  return cards.value.filter(
    (c) =>
      c.status === 1 &&
      c.card_type === "count" &&
      (c.remaining_credits ?? 0) === 0,
  );
});

// 待激活的卡（status === 0）
const pendingCards = computed(() => {
  return cards.value.filter((c) => c.status === 0);
});

// 已过期的卡（status === 2）
const expiredCards = computed(() => {
  return cards.value.filter((c) => c.status === 2);
});

// 已作废的卡（status === 6）
const voidedCards = computed(() => {
  return cards.value.filter((c) => c.status === 6);
});

// 冻结中的卡（status === 3）
const frozenCards = computed(() => {
  return cards.value.filter((c) => c.status === 3);
});

// 有效卡（使用中的卡 + 已用完的卡 + 待激活的卡 + 冻结中的卡）
const validCards = computed(() => {
  return [
    ...activeCards.value,
    ...usedUpCards.value,
    ...pendingCards.value,
    ...frozenCards.value,
  ];
});

// 无效卡（过期或作废的卡）
const invalidCards = computed(() => {
  return [...expiredCards.value, ...voidedCards.value];
});

// 获取期卡剩余天数
// 对于未激活的卡：从 valid_from 到 expire_at 的天数（总有效期）
// 对于已激活的卡：从今天到 expire_at 的天数（剩余有效期）
const getValidDays = (card: MembershipCard) => {
  if (!card?.expire_at) return 0;

  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const expireDay = new Date(
    new Date(card.expire_at).getFullYear(),
    new Date(card.expire_at).getMonth(),
    new Date(card.expire_at).getDate(),
  );

  // 未激活的卡：从 valid_from 开始计算总有效期
  let startDay = today;
  if (card.status === 0 && card.valid_from) {
    startDay = new Date(
      new Date(card.valid_from).getFullYear(),
      new Date(card.valid_from).getMonth(),
      new Date(card.valid_from).getDate(),
    );
  }

  const diffMs = expireDay.getTime() - startDay.getTime();
  if (diffMs < 0) return 0;
  // +1 是因为需要包含起始日和结束日（闭区间计算）
  return Math.round(diffMs / (1000 * 60 * 60 * 24)) + 1;
};

// 检查卡片是否因课程类型冲突而无法激活
const getActivationBlockReason = (card: MembershipCard): string | null => {
  // 只有次卡、期卡、无限卡需要检查课程类型冲突
  if (!card.applicable_course_type_code) return null;

  // 查找所有使用中的卡
  const activeCardsList = cards.value.filter((c) => c.status === 1);

  // 检查是否有相同课程类型的使用中卡
  for (const activeCard of activeCardsList) {
    if (
      activeCard.applicable_course_type_code ===
      card.applicable_course_type_code
    ) {
      // 获取课程类型名称（从 code 推断）
      const typeName = getCourseTypeName(card.applicable_course_type_code);
      return `已有${typeName}在使用中，无法激活`;
    }
  }

  return null;
};

// 根据课程类型 code 获取名称
const getCourseTypeName = (code: string): string => {
  const nameMap: Record<string, string> = {
    regular: "常规课",
    special: "特色课",
    private: "私教课",
  };
  return nameMap[code] || code;
};

// 激活卡片
const handleActivate = async (card: MembershipCard) => {
  uni.showModal({
    title: "确认激活",
    content: `确定要激活「${card.product_name || "会员卡"}」吗？`,
    success: async (res) => {
      if (res.confirm) {
        try {
          uni.showLoading({ title: "激活中..." });
          await membershipApi.activateCard(card.id);
          uni.hideLoading();
          uni.showToast({ title: "激活成功", icon: "success" });
          // 重新加载卡片列表
          await loadCards();
        } catch (error) {
          uni.hideLoading();
          console.error("激活失败:", error);
        }
      }
    },
  });
};

// 提前解冻卡片
const handleUnfreeze = async (card: MembershipCard) => {
  uni.showModal({
    title: "确认解冻",
    content: `确定要提前解冻「${card.product_name || "会员卡"}」吗？解冻后卡片将恢复正常使用。`,
    success: async (res) => {
      if (res.confirm) {
        try {
          uni.showLoading({ title: "解冻中..." });
          await membershipApi.studentUnfreeze(card.id);
          uni.hideLoading();
          uni.showToast({ title: "解冻成功", icon: "success" });
          // 重新加载卡片列表
          await loadCards();
        } catch (error: any) {
          uni.hideLoading();
          const errorMsg =
            error?.response?.data?.detail ||
            error?.response?.data?.msg ||
            "解冻失败";
          uni.showToast({ title: errorMsg, icon: "none" });
          console.error("解冻失败:", error);
        }
      }
    },
  });
};

// 复制卡号
const copyCardNo = (cardNo: string | undefined) => {
  if (!cardNo) return;
  uni.setClipboardData({
    data: cardNo,
    success: () => {
      uni.showToast({ title: "卡号已复制", icon: "success" });
    },
  });
};

onMounted(() => {
  if (!checkLogin("student")) return;
  loadCards();
});

const loadCards = async () => {
  try {
    loading.value = true;
    const res = await membershipApi.getMyCards();
    const responseData = res?.data as any;
    if (responseData?.items && Array.isArray(responseData.items)) {
      cards.value = responseData.items;
    } else if (Array.isArray(responseData)) {
      cards.value = responseData;
    } else if (responseData) {
      cards.value = [responseData];
    }
  } catch (error) {
    console.error("加载会员卡失败:", error);
    uni.showToast({ title: "加载失败", icon: "none" });
  } finally {
    loading.value = false;
  }
};

const formatDateShort = (dateStr: string | null) => {
  if (!dateStr) return "-";
  const d = new Date(dateStr);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const goToHandle = () => {
  uni.showToast({
    title: "请联系管理员办理会员卡",
    icon: "none",
    duration: 2000,
  });
};
</script>

<style lang="scss">
.membership_container {
  @include page-container;
  background: linear-gradient(180deg, #faf6f0 0%, #f5ede3 100%);
  display: flex;
  flex-direction: column;
  height: 100vh;
}

// ===== 顶部筛选标签（固定） =====
.filter-tabs {
  display: flex;
  gap: $space-sm;
  padding: $space-md;
  background: transparent;
  flex-shrink: 0;
}

.filter-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20rpx 0;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 50rpx;
  border: 1rpx solid rgba(201, 166, 107, 0.15);
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.03);
  transition: all 0.3s ease;

  .tab-text {
    font-size: 28rpx;
    color: #b8a088;
    font-weight: 500;
  }

  &.tab-active {
    background: linear-gradient(135deg, #d4b896 0%, #c9a66b 100%);
    border-color: transparent;
    box-shadow: 0 4rpx 20rpx rgba(201, 166, 107, 0.35);

    .tab-text {
      color: #fff;
      font-weight: 600;
    }
  }
}

// ===== 可滚动区域 =====
.cards-scroll {
  flex: 1;
  height: 0;
  padding: 0 $space-md;
  padding-bottom: 40rpx;
  box-sizing: border-box;
}

// ===== 卡片通用样式 =====
.cards-section {
  display: flex;
  flex-direction: column;
  gap: $space-sm;
}

.card-item {
  border-radius: $radius-lg;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.05);
  overflow: hidden;
  transition: all 0.3s ease;

  &.card-active {
    background: linear-gradient(
      135deg,
      #fdf6e9 0%,
      #f9edda 30%,
      #f5e6c8 60%,
      #f0d9a8 100%
    );
    box-shadow: 0 4rpx 20rpx rgba(201, 166, 107, 0.2);
    position: relative;
    border: 1rpx solid rgba(201, 166, 107, 0.2);
  }

  &.card-used-up {
    background: linear-gradient(135deg, #faf8f5 0%, #f7f3ed 100%);
    border: 1rpx solid rgba(201, 166, 107, 0.1);
  }

  &.card-pending {
    background: linear-gradient(135deg, #faf8f5 0%, #f7f3ed 100%);
    border: 1rpx solid rgba(201, 166, 107, 0.1);
  }

  &.card-frozen {
    background: linear-gradient(135deg, #f5f7fa 0%, #eef1f5 100%);
    border: 1rpx solid rgba(100, 149, 237, 0.15);
  }

  &.card-expired {
    background: linear-gradient(135deg, #f8f6f3 0%, #f3f0eb 100%);
    opacity: 0.65;
    border: 1rpx solid rgba(200, 200, 200, 0.15);
  }
}

.card-content {
  display: flex;
  padding: $space-md;
  gap: $space-sm;
  position: relative;
}

// 中间内容
.card-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-name {
  font-size: $font-size-body;
  font-weight: $font-weight-bold;
  color: #333;
  flex: 1;

  .card-active & {
    color: #333;
  }
}

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

.card-no-row {
  display: flex;
  align-items: center;
  gap: 8rpx;

  .card-no-label {
    font-size: $font-size-caption;
    color: #999;

    .card-active & {
      color: rgba(90, 74, 42, 0.6);
    }
  }

  .card-no-text {
    font-size: $font-size-caption;
    color: #999;

    .card-active & {
      color: rgba(90, 74, 42, 0.6);
    }
  }

  .copy-icon-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 4rpx;
    cursor: pointer;
  }
}

// 使用信息
.card-usage {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.usage-main {
  display: flex;
  align-items: baseline;
  gap: 8rpx;

  &.usage-main-expired {
    gap: 12rpx;
  }

  .usage-label {
    font-size: $font-size-caption;
    color: #999;

    .card-active & {
      color: rgba(90, 74, 42, 0.7);
    }
  }

  .usage-value-row {
    display: flex;
    align-items: baseline;
    gap: 4rpx;

    .usage-value {
      font-size: $font-size-h3;
      font-weight: $font-weight-bold;
      color: #333;

      .card-active & {
        color: #333;
      }

      &.usage-value-zero {
        color: #333;
      }
    }

    .usage-unit {
      font-size: $font-size-caption;
      color: #999;

      .card-active & {
        color: rgba(90, 74, 42, 0.6);
      }
    }
  }

  .usage-divider-line {
    width: 1rpx;
    height: 24rpx;
    background: #ddd;

    .card-active & {
      background: rgba(90, 74, 42, 0.3);
    }
  }

  // 剩余次数 / 总次数 高级展示样式
  .credits-display {
    display: flex;
    align-items: baseline;
    gap: 6rpx;

    .credits-label {
      font-size: $font-size-caption;
      color: #999;

      .card-active & {
        color: rgba(90, 74, 42, 0.6);
      }
    }

    .credits-remaining {
      font-size: 56rpx;
      font-weight: 700;
      color: #c9a66b;
      line-height: 1;
      font-family: "DIN Alternate", "Helvetica Neue", sans-serif;

      .card-active & {
        color: #c9a66b;
      }

      &.usage-value-zero {
        color: #ef5350;
      }
    }

    .credits-separator {
      font-size: 36rpx;
      font-weight: 300;
      color: #bbb;
      margin: 0 2rpx;
    }

    .credits-total {
      font-size: 36rpx;
      font-weight: 600;
      color: #999;
      line-height: 1;

      .card-active & {
        color: rgba(90, 74, 42, 0.6);
      }
    }

    .credits-unit {
      font-size: $font-size-caption;
      color: #999;
      margin-left: 2rpx;

      .card-active & {
        color: rgba(90, 74, 42, 0.6);
      }
    }
  }

  .usage-total-row {
    display: flex;
    align-items: baseline;
    gap: 4rpx;

    .usage-total-label {
      font-size: $font-size-caption;
      color: #999;

      .card-active & {
        color: rgba(90, 74, 42, 0.6);
      }
    }

    .usage-total-value {
      font-size: $font-size-body;
      font-weight: $font-weight-bold;
      color: #333;

      .card-active & {
        color: #333;
      }
    }

    .usage-total-unit {
      font-size: $font-size-caption;
      color: #999;

      .card-active & {
        color: rgba(90, 74, 42, 0.6);
      }
    }
  }

  .usage-total-inline {
    font-size: $font-size-caption;
    color: #999;

    .card-active & {
      color: rgba(90, 74, 42, 0.6);
    }
  }

  .usage-infinity {
    font-size: $font-size-h3;
    color: #c9a66b;
    font-weight: bold;
  }

  .usage-unlimited-text {
    font-size: $font-size-body;
    color: #666;

    .card-active & {
      color: rgba(90, 74, 42, 0.8);
    }
  }

  .usage-valid-range {
    font-size: $font-size-caption;
    color: #999;
    flex-shrink: 0;

    .card-active & {
      color: rgba(90, 74, 42, 0.6);
    }
  }

  .usage-frozen-text {
    font-size: $font-size-body;
    color: #6495ed;
    font-weight: $font-weight-medium;
  }

  .usage-frozen-reason {
    font-size: $font-size-caption;
    color: #999;
  }

  .usage-frozen-until-label {
    font-size: $font-size-caption;
    color: #999;
  }

  .usage-frozen-until {
    font-size: $font-size-caption;
    color: #6495ed;
    font-weight: $font-weight-medium;
  }
}

// 进度条
.progress-row {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.progress-bar {
  flex: 1;
  height: 8rpx;
  background: rgba(0, 0, 0, 0.05);
  border-radius: 4rpx;
  overflow: hidden;

  .card-active & {
    background: rgba(90, 74, 42, 0.1);
  }

  .progress-fill {
    height: 100%;
    border-radius: 4rpx;
    transition: width 0.3s ease;

    &.progress-fill-active {
      background: linear-gradient(90deg, #c9a66b 0%, #d4b896 50%, #e0c9a0 100%);
    }

    &.progress-fill-empty {
      background: #e8e4de;
    }
  }
}

.progress-text {
  font-size: $font-size-caption;
  color: #999;
  flex-shrink: 0;

  .card-active & {
    color: rgba(90, 74, 42, 0.7);
  }
}

// 未激活警告框
.activation-warning-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16rpx $space-md;
  background: rgba(255, 152, 0, 0.08);
  margin: 0 $space-md $space-md;
  border-radius: $radius-sm;

  .warning-left {
    display: flex;
    align-items: center;
    gap: 12rpx;
    flex: 1;

    .warning-icon-circle {
      width: 32rpx;
      height: 32rpx;
      border-radius: 50%;
      background: #c9a66b;
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20rpx;
      font-weight: bold;
      flex-shrink: 0;
    }

    .warning-text-content {
      display: flex;
      flex-direction: column;
      gap: 4rpx;

      .warning-title {
        font-size: $font-size-caption;
        color: #c9a66b;
        font-weight: $font-weight-medium;
      }

      .warning-desc {
        font-size: 20rpx;
        color: rgba(201, 166, 107, 0.7);
      }
    }
  }

  .warning-link {
    font-size: $font-size-caption;
    color: #c9a66b;
    flex-shrink: 0;
  }
}

// 可激活卡：使用信息 + 激活按钮同行
.usage-with-activate {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.usage-inline {
  flex: 1;
  min-width: 0;
}

.activate-btn-inline {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12rpx 24rpx;
  background: linear-gradient(135deg, #d4b896 0%, #c9a66b 100%);
  border-radius: 32rpx;
  box-shadow: 0 2rpx 12rpx rgba(201, 166, 107, 0.3);
  flex-shrink: 0;
  transition: all 0.2s ease;

  &:active {
    transform: scale(0.95);
    opacity: 0.9;
  }

  .activate-btn-text {
    font-size: $font-size-caption;
    color: #fff;
    font-weight: $font-weight-medium;
  }
}

// 冻结卡：使用信息 + 提前解冻按钮同行
.usage-with-unfreeze {
  display: flex;
  align-items: center;
  gap: 12rpx;
  min-width: 0;

  .card-usage {
    flex: 1;
    min-width: 0;
  }
}

.unfreeze-btn-inline {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12rpx 24rpx;
  background: linear-gradient(135deg, #6495ed 0%, #4a7bd4 100%);
  border-radius: 32rpx;
  box-shadow: 0 2rpx 12rpx rgba(100, 149, 237, 0.3);
  flex-shrink: 0;
  transition: all 0.2s ease;

  &:active {
    transform: scale(0.95);
    opacity: 0.9;
  }

  .unfreeze-btn-text {
    font-size: $font-size-caption;
    color: #fff;
    font-weight: $font-weight-medium;
  }
}

// ===== 无效卡标题 =====
.invalid-section-title {
  display: flex;
  align-items: center;
  gap: $space-xs;
  padding: $space-sm 0;
  margin-bottom: $space-xs;

  .title-bar {
    width: 6rpx;
    height: 28rpx;
    background: #c9a66b;
    border-radius: 3rpx;
  }

  .title-text {
    font-size: $font-size-body;
    font-weight: $font-weight-bold;
    color: #333;
  }

  .title-count {
    font-size: $font-size-body_sm;
    color: #999;
  }

  .title-line {
    flex: 1;
    height: 1rpx;
    background: linear-gradient(90deg, rgba(201, 166, 107, 0.3), transparent);
  }
}

// ===== 空状态 =====
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60rpx $space-md 40rpx;
  gap: 24rpx;

  .empty-card-illustration {
    position: relative;
    width: 280rpx;
    height: 200rpx;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 16rpx;

    .card-3d {
      position: relative;
      width: 160rpx;
      height: 100rpx;

      .card-face {
        position: relative;
        width: 160rpx;
        height: 100rpx;
        background: linear-gradient(
          135deg,
          #f5e6c8 0%,
          #e8d5b7 50%,
          #d4b896 100%
        );
        border-radius: 16rpx;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 8rpx 32rpx rgba(201, 166, 107, 0.3);
        transform: rotate(-8deg);
        z-index: 2;

        &.card-face-invalid {
          background: linear-gradient(
            135deg,
            #f0ebe3 0%,
            #e8e0d5 50%,
            #ddd5c8 100%
          );
          box-shadow: 0 8rpx 32rpx rgba(184, 160, 136, 0.2);
        }
      }

      .card-shadow {
        position: absolute;
        bottom: -16rpx;
        left: 50%;
        transform: translateX(-50%);
        width: 140rpx;
        height: 20rpx;
        background: radial-gradient(
          ellipse,
          rgba(201, 166, 107, 0.2) 0%,
          transparent 70%
        );
        border-radius: 50%;
      }
    }

    .sparkles {
      position: absolute;
      width: 100%;
      height: 100%;
      pointer-events: none;

      .sparkle {
        position: absolute;
        font-size: 24rpx;
        color: #c9a66b;
        opacity: 0.6;
        animation: sparkle-float 3s ease-in-out infinite;

        &.sparkle-1 {
          top: 10rpx;
          left: 20rpx;
          animation-delay: 0s;
        }

        &.sparkle-2 {
          top: 30rpx;
          right: 30rpx;
          animation-delay: 1s;
        }

        &.sparkle-3 {
          bottom: 30rpx;
          left: 40rpx;
          animation-delay: 2s;
        }
      }
    }
  }

  .empty-title {
    font-size: $font-size-h3;
    font-weight: $font-weight-bold;
    color: #333;
  }

  .empty-desc {
    font-size: $font-size-body_sm;
    color: #999;
  }

  .go-handle-btn {
    display: flex;
    align-items: center;
    gap: 8rpx;
    padding: 20rpx 40rpx;
    background: linear-gradient(135deg, #d4b896 0%, #c9a66b 100%);
    border-radius: 50rpx;
    border: none;
    font-size: $font-size-body;
    color: #fff;
    font-weight: $font-weight-medium;
    box-shadow: 0 4rpx 16rpx rgba(201, 166, 107, 0.3);

    .btn-arrow {
      font-size: 32rpx;
    }
  }

  .benefits-section {
    width: 100%;
    margin-top: 40rpx;

    .benefits-title {
      display: block;
      font-size: $font-size-body;
      color: #666;
      text-align: center;
      margin-bottom: $space-md;
    }

    .benefits-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: $space-md;

      .benefit-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 12rpx;

        .benefit-text {
          font-size: $font-size-caption;
          color: #666;
          text-align: center;
        }
      }
    }
  }
}

@keyframes sparkle-float {
  0%,
  100% {
    transform: translateY(0) scale(1);
    opacity: 0.6;
  }
  50% {
    transform: translateY(-10rpx) scale(1.2);
    opacity: 1;
  }
}
</style>
