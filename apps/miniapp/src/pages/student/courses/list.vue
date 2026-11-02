<template>
  <view class="courses-list-page">
    <AppNavbar title="全部课程" />
    <scroll-view class="main-content" scroll-y>
      <!-- 加载状态 -->
      <view v-if="loading && courses.length === 0" class="loading-container">
        <AppLoading type="skeleton" />
      </view>

      <!-- 空状态 -->
      <AppEmpty
        v-else-if="!loading && courses.length === 0"
        icon="📚"
        title="暂无课程"
        description="当前还没有课程，请稍后再试"
      />

      <!-- 课程列表 -->
      <view v-else class="course-list">
        <view
          v-for="(course, index) in courses"
          :key="course.id"
          class="course-item"
          :style="{ animationDelay: `${index * 0.04}s` }"
          @tap="goToCourseDetail(course.id)"
        >
          <!-- 课程图片 -->
          <view class="course-image">
            <image
              v-if="course.cover_url"
              :src="course.cover_url"
              mode="aspectFill"
              class="cover-image"
            />
            <!-- 无封面时使用与首页一致的默认封面 -->
            <image
              v-else
              src="/static/images/default-course-cover.jpg"
              mode="aspectFill"
              class="cover-image"
            />
          </view>

          <!-- 课程信息 -->
          <view class="course-info">
            <text class="course-name">{{ course.name }}</text>
            <text class="course-desc">{{
              course.description || "能力素质训练是一门新手小白的入门必..."
            }}</text>
          </view>
        </view>
      </view>

      <!-- 底部安全距离 -->
      <view class="bottom-spacer"></view>
    </scroll-view>
  </view>
</template>

<script setup lang="ts">
import { studentApi } from "@/api";
import AppEmpty from "@/components/AppEmpty.vue";
import AppLoading from "@/components/AppLoading.vue";
import AppNavbar from "@/components/AppNavbar.vue";
import { checkLogin } from "@/utils/auth";
import { extractList } from "@/utils/helpers";
import { navigateTo } from "@/utils/navigation";
import { onMounted, ref } from "vue";

const courses = ref<any[]>([]);
const loading = ref(false);

onMounted(() => {
  if (!checkLogin("student")) return;
  loadCourses();
});

const loadCourses = async () => {
  loading.value = true;
  try {
    const result = await studentApi.getCourses({});
    if (result.code === 0 || result.code === 200) {
      courses.value = extractList(result);
    }
  } catch (err) {
    console.error("❌ 课程列表请求异常:", err);
  } finally {
    loading.value = false;
  }
};

const goToCourseDetail = (id: number) => {
  navigateTo({ url: `/pages/student/courses/detail?id=${id}` });
};
</script>

<style lang="scss" scoped>
@import "@/styles/theme/_variables.scss";
@import "@/styles/theme/_mixins.scss";

.courses-list-page {
  @include page-container;
}

.main-content {
  @include main-content;
  padding: 0;
  padding-bottom: env(safe-area-inset-bottom);
}

.loading-container {
  padding: $space-xl $space-md;
}

.course-list {
  padding: $space-md;
  display: flex;
  flex-direction: column;
  gap: $space-md;

  .course-item {
    display: flex;
    gap: $space-md;
    padding: $space-md;
    background: rgba(255, 255, 255, 0.92);
    border-radius: $radius-lg;
    border: 1rpx solid rgba(201, 166, 107, 0.12);
    box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.04);
    animation: cardFadeIn 0.35s cubic-bezier(0.22, 0.61, 0.36, 1) both;

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

    .course-image {
      width: 160rpx;
      height: 160rpx;
      border-radius: $radius-md;
      overflow: hidden;
      flex-shrink: 0;

      .cover-image {
        width: 100%;
        height: 100%;
      }

      .cover-placeholder {
        @include flex-center;
        position: relative;
        width: 100%;
        height: 100%;
        background: linear-gradient(
          135deg,
          #2d2418 0%,
          #1a1612 50%,
          #2d2418 100%
        );
        overflow: hidden;

        .placeholder-bg-gradient {
          position: absolute;
          inset: 0;
          background:
            radial-gradient(
              ellipse 300rpx 200rpx at 70% 30%,
              rgba(201, 166, 107, 0.15) 0%,
              transparent 60%
            ),
            radial-gradient(
              ellipse 250rpx 180rpx at 30% 70%,
              rgba(217, 167, 176, 0.1) 0%,
              transparent 55%
            ),
            linear-gradient(
              155deg,
              #1a1612 0%,
              #2d2418 35%,
              #1f1a14 65%,
              #1a1612 100%
            );
        }

        .placeholder-mesh {
          position: absolute;
          border-radius: 50%;
          filter: blur(36rpx);
          opacity: 0.45;

          &.mesh-1 {
            top: -15%;
            right: -10%;
            width: 240rpx;
            height: 240rpx;
            background: radial-gradient(
              circle at 40% 40%,
              rgba(201, 166, 107, 0.25),
              rgba(201, 166, 107, 0.04)
            );
          }

          &.mesh-2 {
            bottom: -10%;
            left: -10%;
            width: 200rpx;
            height: 200rpx;
            background: radial-gradient(
              circle at 60% 60%,
              rgba(217, 167, 176, 0.2),
              rgba(217, 167, 176, 0.03)
            );
          }
        }

        .placeholder-accent-shape {
          position: absolute;
          top: 12%;
          right: 8%;
          width: 80rpx;
          height: 80rpx;
          border: 1.5rpx solid rgba(201, 166, 107, 0.25);
          border-radius: 50%;
          opacity: 0.6;
        }

        .placeholder-brand-text {
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%) rotate(-8deg);
          font-size: 52rpx;
          font-weight: 700;
          font-style: italic;
          color: rgba(201, 166, 107, 0.12);
          letter-spacing: 6rpx;
          white-space: nowrap;
          pointer-events: none;
        }

        .placeholder-dot-grid {
          position: absolute;
          inset: 0;
          background-image: radial-gradient(
            rgba(201, 166, 107, 0.05) 1rpx,
            transparent 1rpx
          );
          background-size: 20rpx 20rpx;
          opacity: 0.4;
        }
      }
    }

    .course-info {
      flex: 1;
      min-width: 0;

      .course-name {
        display: block;
        font-size: 30rpx;
        font-weight: 600;
        color: #3d2e1f;
        margin-bottom: 8rpx;
        @include text-clamp(1);
      }

      .course-desc {
        display: block;
        font-size: 24rpx;
        color: #8b7355;
        line-height: 1.5;
        @include text-clamp(2);
      }
    }
  }
}

.bottom-spacer {
  height: $space-lg;
}
</style>
