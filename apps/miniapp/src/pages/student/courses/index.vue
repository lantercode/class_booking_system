<template>
  <view class="home-page">
    <!-- 自定义导航栏 -->
    <AppNavbar title="" :show-back="false" variant="default">
      <template #left>
        <view class="location-selector">
          <text class="location-icon"></text>
          <text class="location-text">{{
            tenantName || "舞蹈艺术培训中心"
          }}</text>
          <text class="location-arrow"></text>
        </view>
      </template>
    </AppNavbar>

    <!-- 主内容区域 -->
    <scroll-view class="main-content" scroll-y>
      <!-- Banner轮播区域 -->
      <view class="banner-section">
        <swiper
          class="banner-swiper"
          :indicator-dots="true"
          :autoplay="true"
          :interval="4000"
          :duration="500"
          indicator-color="rgba(255, 255, 255, 0.4)"
          indicator-active-color="#c9a66b"
          circular
        >
          <swiper-item v-for="(banner, index) in banners" :key="index">
            <view class="banner-slide">
              <image
                :src="banner.imageUrl"
                mode="aspectFill"
                class="banner-cover-image"
              />
              <view class="banner-overlay"></view>
              <view class="banner-content">
                <text class="banner-title">{{ banner.title }}</text>
                <text class="banner-subtitle">{{ banner.subtitle }}</text>
              </view>
            </view>
          </swiper-item>
        </swiper>
      </view>

      <!-- 师资团队 -->
      <view class="teachers-section">
        <view class="section-header">
          <view class="section-title">
            <text class="title-icon"></text>
            <text class="title-text">师资团队</text>
          </view>
        </view>

        <!-- 加载状态 -->
        <view v-if="teachersLoading" class="teachers-loading">
          <AppLoading type="skeleton" />
        </view>

        <!-- 教师列表 - 横向滚动 -->
        <scroll-view
          v-else-if="teachers.length > 0"
          class="teachers-scroll"
          scroll-x
          :show-scrollbar="false"
        >
          <view class="teachers-list">
            <view
              v-for="teacher in teachers"
              :key="teacher.id"
              class="teacher-item"
              @tap="goToTeacherDetail(teacher.id)"
            >
              <view class="teacher-avatar">
                <image
                  v-if="teacher.avatar_url"
                  :src="teacher.avatar_url"
                  mode="aspectFill"
                  class="avatar-image"
                />
                <view v-else class="avatar-placeholder">
                  <text class="avatar-text">{{
                    (teacher.nickname || "教").charAt(0)
                  }}</text>
                </view>
              </view>
              <view class="teacher-info">
                <text class="teacher-name">{{
                  teacher.nickname || "未知教师"
                }}</text>
                <text class="teacher-specialty">{{
                  getTeacherSpecialty(teacher)
                }}</text>
              </view>
            </view>
          </view>
        </scroll-view>
      </view>

      <!-- 推荐课程 -->
      <view class="courses-section">
        <view class="section-header">
          <view class="section-title">
            <text class="title-icon"></text>
            <text class="title-text">推荐课程</text>
          </view>
          <view class="section-more" @tap="goToAllCourses">
            <text class="more-text">全部课程</text>
            <text class="more-arrow">›</text>
          </view>
        </view>

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
            v-for="(course, index) in courses.slice(0, 3)"
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
              <image
                v-else
                :src="getCoursePlaceholderImage(course.name)"
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

        <!-- 舞蹈视频区域 -->
        <view class="videos-section">
          <view class="section-header">
            <view class="section-title">
              <text class="title-icon"></text>
              <text class="title-text">舞动 · 让生活更美好</text>
            </view>
          </view>

          <!-- 视频列表 -->
          <view class="video-list">
            <view
              v-for="(video, index) in videos.slice(0, 3)"
              :key="index"
              class="video-card"
              @tap="playVideo(video)"
            >
              <view class="video-cover">
                <image
                  :src="video.coverUrl"
                  mode="aspectFill"
                  class="cover-image"
                />
                <view class="video-overlay">
                  <view class="play-button">
                    <text class="play-icon">▶</text>
                  </view>
                  <text class="video-duration">{{ video.duration }}</text>
                </view>
              </view>
              <view class="video-info">
                <text class="video-title">{{ video.title }}</text>
                <text class="video-desc">{{ video.description }}</text>
              </view>
            </view>
          </view>
        </view>

        <!-- 底部安全距离 -->
        <view class="bottom-spacer"></view>
      </view>
    </scroll-view>

    <!-- 底部导航栏 -->
    <HomeTabBar currentRoute="/pages/student/courses/index" />

    <!-- AI 智能助手 -->
    <AiAssistant :session-id="'student_' + (userId || 'default')" />
  </view>
</template>

<script setup lang="ts">
import { studentApi, teacherApi, tenantApi } from "@/api";
import AiAssistant from "@/components/AiAssistant.vue";
import AppEmpty from "@/components/AppEmpty.vue";
import AppLoading from "@/components/AppLoading.vue";
import AppNavbar from "@/components/AppNavbar.vue";
import HomeTabBar from "@/components/HomeTabBar.vue";
import { checkLogin } from "@/utils/auth";
import { extractList } from "@/utils/helpers";
import { navigateTo } from "@/utils/navigation";
import { nextTick, onMounted, onUnmounted, ref } from "vue";

const courses = ref<any[]>([]);
const loading = ref(false);
const userId = ref("");
const tenantName = ref("");

const teachers = ref<any[]>([]);
const teachersLoading = ref(false);

const videos = ref([
  {
    title: "中国古典舞《身韵》基础教学",
    description: "学习古典舞核心身韵技巧，感受东方美学韵味",
    duration: "03:28",
    coverUrl:
      "https://images.unsplash.com/photo-1518834107812-67b0b7c58434?w=800&q=80",
    videoUrl: "https://www.w3schools.com/html/mov_bbb.mp4",
  },
  {
    title: "古典舞水袖技巧入门",
    description: "掌握水袖基本功，展现柔美飘逸的舞姿",
    duration: "04:15",
    coverUrl:
      "https://images.unsplash.com/photo-1508700929628-666bc8bd84ea?w=800&q=80",
    videoUrl: "https://www.w3schools.com/html/mov_bbb.mp4",
  },
  {
    title: "中国舞气息与身法训练",
    description: "以气带形，以形传神，体会中国舞独特韵味",
    duration: "05:02",
    coverUrl:
      "https://images.unsplash.com/photo-1547153760-18fc86324498?w=800&q=80",
    videoUrl: "https://www.w3schools.com/html/mov_bbb.mp4",
  },
]);

const banners = ref([
  {
    title: "让舞蹈成为生活的一部分",
    subtitle: "遇见更好的自己 · 从一堂舞蹈课开始",
    imageUrl:
      "https://images.unsplash.com/photo-1518834107812-67b0b7c58434?w=1200&q=80",
  },
  {
    title: "专业师资团队",
    subtitle: "资深舞蹈教师 · 一对一指导",
    imageUrl:
      "https://images.unsplash.com/photo-1508700929628-666bc8bd84ea?w=1200&q=80",
  },
  {
    title: "多元化课程体系",
    subtitle: "古典舞 · 现代舞 · 街舞 · 芭蕾",
    imageUrl:
      "https://images.unsplash.com/photo-1547153760-18fc86324498?w=1200&q=80",
  },
  {
    title: "优雅的艺术空间",
    subtitle: "专业舞蹈教室 · 舒适学习环境",
    imageUrl:
      "https://images.unsplash.com/photo-1504609813442-a8924e83f76e?w=1200&q=80",
  },
  {
    title: "开启你的舞蹈之旅",
    subtitle: "零基础入门 · 进阶提升 · 专业表演",
    imageUrl:
      "https://images.unsplash.com/photo-1535525153412-5a42439a210d?w=1200&q=80",
  },
]);

// 加载锁（防止并发请求）
let isLoadingCourses = false;
// 页面卸载标记
let isUnmounted = false;

onMounted(() => {
  if (!checkLogin("student")) return;

  const userInfo = uni.getStorageSync("user_info");
  if (userInfo) {
    try {
      const parsed = JSON.parse(userInfo);
      userId.value = parsed.id || "";
    } catch {}
  }

  loadTenantInfo();
  loadTeachers();
  loadCourses();
});

onUnmounted(() => {
  isUnmounted = true;
});

const loadTenantInfo = async () => {
  try {
    const result = await tenantApi.getInfo();
    if ((result.code === 0 || result.code === 200) && result.data) {
      tenantName.value = result.data.name || "";
      // 存储到本地缓存
      uni.setStorageSync("tenant_name", tenantName.value);
    }
  } catch (err) {
    console.error("加载租户信息失败:", err);
    // 尝试从缓存读取
    const cachedName = uni.getStorageSync("tenant_name");
    if (cachedName) {
      tenantName.value = cachedName;
    }
  }
};

const loadTeachers = async () => {
  teachersLoading.value = true;
  try {
    const result = await teacherApi.list();
    if ((result.code === 0 || result.code === 200) && result.data) {
      teachers.value = result.data;
    }
  } catch (err) {
    console.error("加载教师列表失败:", err);
  } finally {
    teachersLoading.value = false;
  }
};

const getTeacherSpecialty = (teacher: any) => {
  if (teacher.specialties && teacher.specialties.length > 0) {
    return teacher.specialties[0];
  }
  return teacher.title || "舞蹈教师";
};

const goToTeacherDetail = (id: number) => {
  navigateTo({ url: `/pages/student/teachers/detail?id=${id}` });
};

const goToAllTeachers = () => {
  navigateTo({ url: "/pages/student/teachers/list" });
};

const playVideo = (video: any) => {
  uni.navigateTo({
    url: `/pages/student/videos/player?url=${encodeURIComponent(video.videoUrl)}&title=${encodeURIComponent(video.title)}`,
  });
};

const goToAllVideos = () => {
  navigateTo({ url: "/pages/student/videos/list" });
};

const loadCourses = async () => {
  // 防重复调用：如果正在加载中，跳过（避免并发请求）
  if (isLoadingCourses) {
    console.warn("⚠️ [Courses] loadCourses 正在执行，跳过重复调用");
    return;
  }

  // 加锁
  isLoadingCourses = true;
  loading.value = true;

  try {
    const params: any = {};

    console.log("===  课程列表 - 开始加载 ===");
    console.log("请求参数:", params);

    const result = await studentApi.getCourses(params);

    // 页面已卸载，不再更新数据
    if (isUnmounted) return;

    console.log("===  课程列表 - API 返回 ===");
    console.log("result.code:", result.code);
    console.log("result.data:", result?.data);

    if (result.code === 0 || result.code === 200) {
      const extractedList = extractList(result);

      console.log(" 解析成功，课程数量:", extractedList.length);

      if (extractedList.length > 0) {
        console.log("\n 前3个课程:");
        extractedList.slice(0, 3).forEach((course: any, index: number) => {
          console.log(
            `[${index + 1}] ${course.name || course.title || "未知课程"} (分类: ${course.category || "未分类"})`,
          );
        });
      }

      // 更新数据
      courses.value = extractedList;

      console.log(
        "\n 课程列表已更新！当前显示:",
        courses.value.length,
        "门课程",
      );

      // 等待Vue渲染完成
      await nextTick();
      console.log(" [Courses] DOM更新完成");
    } else {
      console.error(" 课程列表API错误:", result.code, result.msg);
      uni.showToast({
        title: result.msg || "加载失败",
        icon: "none",
      });
    }
  } catch (err: any) {
    console.error(" 课程列表请求异常:", err);
    uni.showToast({
      title: err.message?.substring(0, 20) || "加载失败,请检查网络",
      icon: "none",
    });
  } finally {
    // 解锁
    isLoadingCourses = false;
    loading.value = false;
    console.log(" [Courses] 加载完成，状态已重置");
  }
};

const goToCourseDetail = (id: number) => {
  navigateTo({ url: `/pages/student/courses/detail?id=${id}` });
};

const goToBooking = () => {
  navigateTo({ url: "/pages/student/bookings/index" });
};

const goToAllCourses = () => {
  navigateTo({ url: "/pages/student/courses/list" });
};

// 根据课程名称获取对应的舞蹈类型占位图片
const getCoursePlaceholderImage = (courseName: string) => {
  const name = courseName || "";

  // 中国舞/古典舞
  if (
    name.includes("中国舞") ||
    name.includes("古典舞") ||
    name.includes("身韵") ||
    name.includes("水袖")
  ) {
    return "https://images.unsplash.com/photo-1518834107812-67b0b7c58434?w=400&q=80";
  }
  // 芭蕾
  if (name.includes("芭蕾")) {
    return "https://images.unsplash.com/photo-1508700929628-666bc8bd84ea?w=400&q=80";
  }
  // 现代舞
  if (name.includes("现代舞") || name.includes("现代")) {
    return "https://images.unsplash.com/photo-1547153760-18fc86324498?w=400&q=80";
  }
  // 街舞
  if (
    name.includes("街舞") ||
    name.includes("hiphop") ||
    name.includes("Hip-Hop")
  ) {
    return "https://images.unsplash.com/photo-1535525153412-5a42439a210d?w=400&q=80";
  }
  // 爵士舞
  if (name.includes("爵士")) {
    return "https://images.unsplash.com/photo-1504609813442-a8924e83f76e?w=400&q=80";
  }
  // 拉丁舞
  if (name.includes("拉丁")) {
    return "https://images.unsplash.com/photo-1508564072968-65f344e9b88c?w=400&q=80";
  }
  // 瑜伽/形体
  if (name.includes("瑜伽") || name.includes("形体")) {
    return "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=400&q=80";
  }

  // 默认优雅舞蹈图片
  return "https://images.unsplash.com/photo-1518834107812-67b0b7c58434?w=400&q=80";
};
</script>

<style lang="scss" scoped>
.home-page {
  @include page-container;
  background: linear-gradient(180deg, #faf6f0 0%, #f5ede3 100%);
}

.main-content {
  @include main-content;
  padding: 0;
  padding-bottom: $tabbar-height-safe;
  height: calc(100vh - var(--navbar-height) - constant(safe-area-inset-bottom));
  height: calc(100vh - var(--navbar-height) - env(safe-area-inset-bottom));

  // 位置选择器
  .location-selector {
    display: flex;
    align-items: center;
    gap: 4rpx;

    .location-icon {
      width: 28rpx;
      height: 28rpx;
      background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%238b7355'%3E%3Cpath d='M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z'/%3E%3C/svg%3E")
        no-repeat center;
      background-size: contain;
    }

    .location-text {
      font-size: 28rpx;
      color: #3d2e1f;
      font-weight: 500;
    }

    .location-arrow {
      font-size: 24rpx;
      color: #8b7355;
    }
  }

  // Banner轮播区域 - 占满头部
  .banner-section {
    margin-bottom: 0;
    padding: 0;

    .banner-swiper {
      width: 100%;
      height: 360rpx;
    }

    .banner-slide {
      position: relative;
      width: 100%;
      height: 100%;
      overflow: hidden;

      .banner-cover-image {
        width: 100%;
        height: 100%;
        display: block;
      }

      .banner-overlay {
        position: absolute;
        inset: 0;
        background: linear-gradient(
          135deg,
          rgba(30, 22, 16, 0.75) 0%,
          rgba(30, 22, 16, 0.4) 50%,
          rgba(30, 22, 16, 0.1) 100%
        );
        z-index: 1;
      }

      .banner-content {
        position: absolute;
        inset: 0;
        display: flex;
        flex-direction: column;
        justify-content: center;
        padding: $space-lg $space-xl;
        z-index: 2;

        .banner-title {
          display: block;
          font-size: 44rpx;
          font-weight: 700;
          color: #fff;
          line-height: 1.4;
          margin-bottom: 16rpx;
          text-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.3);
        }

        .banner-subtitle {
          display: block;
          font-size: 26rpx;
          color: rgba(255, 255, 255, 0.9);
          line-height: 1.5;
          text-shadow: 0 1rpx 4rpx rgba(0, 0, 0, 0.2);
        }
      }
    }
  }

  // 师资团队区域
  .teachers-section {
    padding: $space-lg $space-md 0;
    margin-bottom: $space-lg;

    .section-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: $space-md;

      .section-title {
        display: flex;
        align-items: center;
        gap: 8rpx;

        .title-icon {
          width: 32rpx;
          height: 32rpx;
          background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23c9a66b'%3E%3Cpath d='M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z'/%3E%3C/svg%3E")
            no-repeat center;
          background-size: contain;
        }

        .title-text {
          font-size: 32rpx;
          font-weight: 600;
          color: #3d2e1f;
        }
      }

      .section-more {
        display: flex;
        align-items: center;
        gap: 4rpx;

        .more-text {
          font-size: 24rpx;
          color: #8b7355;
        }

        .more-arrow {
          font-size: 28rpx;
          color: #8b7355;
        }
      }
    }

    .teachers-loading {
      padding: $space-md 0;
    }

    .teachers-scroll {
      white-space: nowrap;
      width: 100%;
    }

    .teachers-list {
      display: inline-flex;
      gap: $space-md;
      padding-bottom: $space-sm;
    }

    .teacher-item {
      display: inline-flex;
      flex-direction: column;
      align-items: center;
      width: 140rpx;
      flex-shrink: 0;

      .teacher-avatar {
        width: 120rpx;
        height: 120rpx;
        border-radius: 50%;
        overflow: hidden;
        margin-bottom: 12rpx;
        border: 2rpx solid rgba(201, 166, 107, 0.3);

        .avatar-image {
          width: 100%;
          height: 100%;
          display: block;
        }

        .avatar-placeholder {
          width: 100%;
          height: 100%;
          background: linear-gradient(135deg, #f5e6d3 0%, #e8d5c4 100%);
          display: flex;
          align-items: center;
          justify-content: center;

          .avatar-text {
            font-size: 36rpx;
            font-weight: 600;
            color: #8b7355;
          }
        }
      }

      .teacher-info {
        text-align: center;
        width: 100%;

        .teacher-name {
          display: block;
          font-size: 26rpx;
          font-weight: 500;
          color: #3d2e1f;
          margin-bottom: 4rpx;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .teacher-specialty {
          display: block;
          font-size: 22rpx;
          color: #8b7355;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }
    }
  }

  // 推荐课程区域
  .courses-section {
    padding: $space-lg $space-md 0;
    margin-bottom: $space-lg;

    .section-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: $space-md;

      .section-title {
        display: flex;
        align-items: center;
        gap: 8rpx;

        .title-icon {
          width: 32rpx;
          height: 32rpx;
          background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23c9a66b'%3E%3Cpath d='M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z'/%3E%3C/svg%3E")
            no-repeat center;
          background-size: contain;
        }

        .title-text {
          font-size: 32rpx;
          font-weight: 600;
          color: #3d2e1f;
        }
      }

      .section-more {
        display: flex;
        align-items: center;
        gap: 4rpx;

        .more-text {
          font-size: 24rpx;
          color: #8b7355;
        }

        .more-arrow {
          font-size: 28rpx;
          color: #8b7355;
        }
      }
    }

    // 加载容器
    .loading-container {
      padding: $space-xl $space-md;
    }

    // 课程列表
    .course-list {
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
          display: flex;
          flex-direction: column;
          justify-content: center;
          min-width: 0;

          .course-name {
            font-size: 30rpx;
            font-weight: 600;
            color: #3d2e1f;
            margin-bottom: 8rpx;
            @include text-clamp(1);
          }

          .course-desc {
            font-size: 24rpx;
            color: #8b7355;
            line-height: 1.5;
            @include text-clamp(2);
          }
        }
      }
    }

    // 舞蹈视频区域
    .videos-section {
      padding: $space-lg 0;
      margin-bottom: $space-lg;

      .section-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: $space-md;

        .section-title {
          display: flex;
          align-items: center;
          gap: 8rpx;

          .title-icon {
            width: 32rpx;
            height: 32rpx;
            background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23c9a66b'%3E%3Cpath d='M8 5v14l11-7z'/%3E%3C/svg%3E")
              no-repeat center;
            background-size: contain;
          }

          .title-text {
            font-size: 32rpx;
            font-weight: 600;
            color: #3d2e1f;
          }
        }

        .section-more {
          display: flex;
          align-items: center;
          gap: 4rpx;

          .more-text {
            font-size: 24rpx;
            color: #8b7355;
          }

          .more-arrow {
            font-size: 28rpx;
            color: #8b7355;
          }
        }
      }

      // 视频列表
      .video-list {
        display: flex;
        flex-direction: column;
        gap: $space-md;
      }

      .video-card {
        background: rgba(255, 255, 255, 0.92);
        border-radius: $radius-lg;
        border: 1rpx solid rgba(201, 166, 107, 0.12);
        box-shadow: 0 4rpx 20rpx rgba(0, 0, 0, 0.04);
        overflow: hidden;

        .video-cover {
          position: relative;
          width: 100%;
          height: 360rpx;
          overflow: hidden;

          .cover-image {
            width: 100%;
            height: 100%;
            display: block;
          }

          .video-overlay {
            position: absolute;
            inset: 0;
            background: linear-gradient(
              180deg,
              rgba(0, 0, 0, 0.1) 0%,
              rgba(0, 0, 0, 0.4) 100%
            );
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 16rpx;

            .play-button {
              width: 100rpx;
              height: 100rpx;
              border-radius: 50%;
              background: rgba(201, 166, 107, 0.9);
              display: flex;
              align-items: center;
              justify-content: center;
              box-shadow: 0 4rpx 20rpx rgba(201, 166, 107, 0.4);

              .play-icon {
                font-size: 36rpx;
                color: #fff;
                margin-left: 6rpx;
              }
            }

            .video-duration {
              font-size: 24rpx;
              color: rgba(255, 255, 255, 0.9);
              background: rgba(0, 0, 0, 0.5);
              padding: 4rpx 16rpx;
              border-radius: 20rpx;
            }
          }
        }

        .video-info {
          padding: $space-md;

          .video-title {
            display: block;
            font-size: 30rpx;
            font-weight: 600;
            color: #3d2e1f;
            margin-bottom: 8rpx;
          }

          .video-desc {
            display: block;
            font-size: 24rpx;
            color: #8b7355;
            line-height: 1.5;
            @include text-clamp(2);
          }
        }
      }
    }

    // 底部安全间距
    .bottom-spacer {
      height: $space-lg;
    }
  }
}
</style>
