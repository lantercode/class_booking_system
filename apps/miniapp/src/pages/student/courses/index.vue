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
    <scroll-view class="main-content" :scroll-y="!scrollLocked">
      <!--
        按后台首页配置的 sort 升序渲染模块：
        banner → teachers → courses → video（notice 与 enabled=false 已在规范化阶段过滤）
      -->
      <template v-for="(m, moduleIndex) in modules" :key="m.type">
        <!-- Banner轮播区域 -->
        <view
          v-if="m.type === 'banner' && m.banners.length > 0"
          class="banner-section"
        >
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
            <swiper-item v-for="(banner, index) in m.banners" :key="index">
              <view class="banner-slide">
                <image
                  :src="banner.imageUrl"
                  mode="aspectFill"
                  class="banner-cover-image"
                />
                <view class="banner-overlay"></view>
                <view class="banner-content">
                  <!-- 标题/副标题为空时不渲染空文本节点，避免占高度 -->
                  <text v-if="banner.title" class="banner-title">{{
                    banner.title
                  }}</text>
                  <!-- 艺术化装饰分割线（金线 + 菱形） -->
                  <view v-if="banner.subtitle" class="banner-divider">
                    <view class="divider-line"></view>
                    <view class="divider-diamond"></view>
                    <view class="divider-line"></view>
                  </view>
                  <text v-if="banner.subtitle" class="banner-subtitle">{{
                    banner.subtitle
                  }}</text>
                </view>
              </view>
            </swiper-item>
          </swiper>
        </view>

        <!-- 师资团队 -->
        <view
          v-else-if="m.type === 'teachers' && teachers.length > 0 && !teachersLoading"
          class="teachers-section"
        >
          <view class="section-header">
            <view class="section-title">
              <text class="title-icon"></text>
              <text class="title-text">师资团队</text>
            </view>
          </view>

          <!-- 教师列表 - 横向滚动 -->
          <scroll-view class="teachers-scroll" scroll-x :show-scrollbar="false">
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
                  <!-- 无头像时展示统一的人形剪影默认头像 -->
                  <view v-else class="avatar-placeholder">
                    <view class="avatar-head"></view>
                    <view class="avatar-body"></view>
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
        <view
          v-else-if="m.type === 'courses' && (courses.length > 0 || (loading && courses.length === 0))"
          class="courses-section"
        >
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
          <view
            v-if="loading && courses.length === 0"
            class="loading-container"
          >
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
                <!-- 无封面时使用统一默认封面 -->
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
        </view>

        <!-- 舞蹈视频区域（独立模块，顺序由后台配置决定） -->
        <view
          v-else-if="m.type === 'video' && m.videos.length > 0"
          class="videos-section"
        >
          <view class="section-header">
            <view class="section-title">
              <text class="title-icon"></text>
              <text class="title-text">舞动 · 让生活更美好</text>
            </view>
          </view>

          <!-- 视频列表 -->
          <view class="video-list">
            <view
              v-for="(video, index) in m.videos.slice(0, 3)"
              :key="index"
              class="video-card"
            >
              <view class="video-cover">
                <!-- 激活后原位替换为原生播放器：小窗内联播放，全屏由微信原生接管（真机自动横屏） -->
                <video
                  v-if="isVideoActive(moduleIndex, index)"
                  :id="`inline-video-${moduleIndex}-${index}`"
                  :src="getVideoSrc(moduleIndex, index, video)"
                  class="inline-video"
                  :autoplay="true"
                  :controls="true"
                  :show-fullscreen-btn="true"
                  :show-center-play-btn="true"
                  :show-progress="true"
                  :enable-progress-gesture="true"
                  object-fit="contain"
                  :poster="video.coverUrl"
                  @play="onVideoPlay"
                  @pause="onVideoPause"
                  @ended="onVideoEnded"
                  @error="onVideoError($event, video, moduleIndex, index)"
                />
                <!-- 未激活时展示封面与播放按钮 -->
                <template v-else>
                  <image
                    :src="video.coverUrl"
                    mode="aspectFill"
                    class="cover-image"
                  />
                  <view
                    class="video-overlay"
                    @tap="startInlinePlay(moduleIndex, index)"
                  >
                    <view class="play-button">
                      <text class="play-icon">▶</text>
                    </view>
                    <!-- 后台配置可能不含时长，无值时不渲染 -->
                    <text v-if="video.duration" class="video-duration">{{
                      video.duration
                    }}</text>
                  </view>
                </template>
              </view>
              <view class="video-info">
                <text class="video-title">{{ video.title }}</text>
                <text v-if="video.description" class="video-desc">{{
                  video.description
                }}</text>
              </view>
            </view>
          </view>
        </view>
      </template>

      <!-- 底部安全距离 -->
      <view class="bottom-spacer"></view>
    </scroll-view>

    <!-- 底部导航栏 -->
    <HomeTabBar currentRoute="/pages/student/courses/index" />
  </view>
</template>

<script setup lang="ts">
import {
  homeConfigApi,
  studentApi,
  teacherApi,
  tenantApi,
  uploadApi,
  type HomeConfigBannerItem,
  type HomeConfigModule,
  type HomeConfigPayload,
  type HomeConfigVideoItem,
  type TeacherListItem,
} from "@/api";
import AppEmpty from "@/components/AppEmpty.vue";
import AppLoading from "@/components/AppLoading.vue";
import AppNavbar from "@/components/AppNavbar.vue";
import HomeTabBar from "@/components/HomeTabBar.vue";
import { checkLogin } from "@/utils/auth";
import { extractList } from "@/utils/helpers";
import { navigateTo } from "@/utils/navigation";
import { onHide } from "@dcloudio/uni-app";
import { onMounted, onUnmounted, ref } from "vue";

/** 页面内部使用的 banner 结构 */
interface BannerView {
  title: string;
  subtitle: string;
  imageUrl: string;
  linkUrl?: string;
}

/** 页面内部使用的视频结构（duration 可能不存在，后台配置不提供时长） */
interface VideoView {
  title: string;
  description: string;
  coverUrl: string;
  videoUrl: string;
  /** 视频 object_key，播放失败时可用于换取新签名地址 */
  videoKey?: string;
  duration?: string;
}

interface BannerModule {
  type: "banner";
  banners: BannerView[];
}

interface TeachersModule {
  type: "teachers";
  teacherIds: number[];
  limit: number;
}

interface CoursesModule {
  type: "courses";
  courseIds: number[];
  limit: number;
}

interface VideoModule {
  type: "video";
  videos: VideoView[];
}

/** 规范化后的首页模块（按 sort 升序渲染） */
type HomeModule = BannerModule | TeachersModule | CoursesModule | VideoModule;

const courses = ref<any[]>([]);
const loading = ref(false);
const userId = ref("");
const tenantName = ref("");
const tenantId = ref(0);

const teachers = ref<TeacherListItem[]>([]);
const teachersLoading = ref(false);

/** 首页模块：配置成功时来自后台，失败 / 未发布时使用内置默认内容 */
const modules = ref<HomeModule[]>([]);

/** 未发布配置时的默认视频内容（保留原页面临时数据作为降级） */
const DEFAULT_VIDEOS: VideoView[] = [
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
];

/** 未发布配置时的默认 banner 内容（保留原页面临时数据作为降级） */
const DEFAULT_BANNERS: BannerView[] = [
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
];

// 页面卸载标记（避免卸载后继续更新数据）
let isUnmounted = false;

/** Banner 毛笔行楷字体族名（需与 WXSS 中 font-family 保持一致） */
const BANNER_FONT_FAMILY = "BannerSerif";

/** 字体对象在 OSS 中的租户内路径（不含 t/{tenant_id}/ 前缀），当前为马善政毛笔体 */
const BANNER_FONT_OBJECT_PATH = "font/MaShanZheng-Banner.woff";

/** 每次启动只加载一次，避免反复申请签名地址 */
let bannerFontLoading: Promise<void> | null = null;

onMounted(() => {
  if (!checkLogin("student")) return;

  const userInfo = uni.getStorageSync("user_info");
  if (userInfo) {
    try {
      const parsed = JSON.parse(userInfo);
      userId.value = parsed.id || "";
    } catch {}
  }

  loadTenantInfo().then(() => {
    if (tenantId.value) {
      loadBannerFont(tenantId.value);
    } else {
      console.warn("[BannerFont] 未获取到租户 ID，跳过字体加载");
    }
  });
  loadHomeConfig();
});

onUnmounted(() => {
  isUnmounted = true;
  stopInlineVideo();
});

const loadTenantInfo = async () => {
  try {
    const result = await tenantApi.getInfo();
    if ((result.code === 0 || result.code === 200) && result.data) {
      tenantName.value = result.data.name || "";
      tenantId.value = Number(result.data.id) || 0;
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

/**
 * 真机微信不认 WXSS 里的系统字体名，必须用 loadFontFace 加载网络字体。
 * 字体存于私有 OSS，先用 /upload/url 换预签名 https 地址再加载；
 * 失败时保持 WXSS 中的系统楷体兜底，不阻塞页面渲染。
 */
const loadBannerFont = (tenantIdValue: number): Promise<void> => {
  if (bannerFontLoading) return bannerFontLoading;

  bannerFontLoading = (async () => {
    try {
      const result = await uploadApi.getUrl(
        `t/${tenantIdValue}/${BANNER_FONT_OBJECT_PATH}`,
      );
      const fontUrl = result.data?.url;
      if (!fontUrl) {
        console.warn("[BannerFont] 未获取到字体预签名地址");
        return;
      }

      await new Promise<void>((resolve) => {
        uni.loadFontFace({
          global: true,
          family: BANNER_FONT_FAMILY,
          source: `url("${fontUrl}")`,
          desc: { style: "normal", weight: "400", variant: "normal" },
          success: () => console.log("[BannerFont] loaded"),
          fail: (err) => console.warn("[BannerFont] fail", err),
          complete: () => resolve(),
        });
      });
    } catch (err) {
      console.warn("Banner 字体加载失败，回退系统楷体:", err);
    }
  })();

  return bannerFontLoading;
};

/** 把 unknown 值安全转为正整数 ID 数组（兼容后台可能传来的字符串 ID） */
const toNumberArray = (value: unknown): number[] => {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => Number(item))
    .filter((id) => Number.isFinite(id) && id > 0);
};

/** 按后台选择的 ids 顺序取数据；未配置 ids 时取前 limit 条 */
const pickByIds = <T extends { id: number }>(
  list: T[],
  ids: number[],
  limit: number,
): T[] => {
  if (!Array.isArray(list)) return [];

  if (ids.length > 0) {
    const idMap = new Map<number, T>();
    list.forEach((item) => idMap.set(item.id, item));
    return ids
      .map((id) => idMap.get(id))
      .filter((item): item is T => Boolean(item))
      .slice(0, limit);
  }

  return list.slice(0, limit);
};

/** 规范化 banner 模块（新格式 icon_url / 旧格式 image_key） */
const normalizeBanner = (m: HomeConfigModule): BannerModule | null => {
  const items = Array.isArray(m.items) ? m.items : [];
  // 旧格式标题在模块顶层，条目内没有 title 时回退到顶层 title
  const topTitle =
    typeof (m as unknown as { title?: unknown }).title === "string"
      ? (m as unknown as { title: string }).title
      : "";

  const banners: BannerView[] = items
    .map((raw) => {
      const item = raw as HomeConfigBannerItem;
      return {
        title: item.title || topTitle,
        subtitle: item.subtitle || "",
        // 后端已把 object_key 解析为完整 URL，这里直接用字段值
        imageUrl: item.image_url || item.image_key || "",
        linkUrl: item.link_url,
      };
    })
    .filter((banner) => Boolean(banner.imageUrl));

  return banners.length > 0 ? { type: "banner", banners } : null;
};

/** 规范化 teachers 模块（新格式 config.teacher_ids / 旧格式顶层 teacher_ids） */
const normalizeTeachers = (m: HomeConfigModule): TeachersModule => {
  const config = (m.config || {}) as {
    teacher_ids?: unknown;
    display_count?: number;
  };
  const teacherIds = toNumberArray(config.teacher_ids ?? m.teacher_ids);
  const limit = config.display_count ?? m.limit ?? 6;
  return { type: "teachers", teacherIds, limit };
};

/** 规范化 courses 模块（新格式 config.course_ids / 旧格式顶层 course_ids） */
const normalizeCourses = (m: HomeConfigModule): CoursesModule => {
  const config = (m.config || {}) as {
    course_ids?: unknown;
    display_count?: number;
  };
  const courseIds = toNumberArray(config.course_ids ?? m.course_ids);
  const limit = config.display_count ?? m.limit ?? 3;
  return { type: "courses", courseIds, limit };
};

/** 规范化 video 模块（新格式 items 数组 / 旧格式 config 单条） */
const normalizeVideo = (m: HomeConfigModule): VideoModule | null => {
  const items = Array.isArray(m.items) ? m.items : [];
  let videos: VideoView[] = [];

  if (items.length > 0) {
    videos = items
      .map((raw) => {
        const item = raw as HomeConfigVideoItem;
        return {
          title: item.title || "",
          description: item.description || "",
          coverUrl: item.cover_url || item.cover_key || "",
          videoUrl: item.video_url || item.video_key || "",
          videoKey: item.video_key || "",
        };
      })
      .filter((video) => Boolean(video.videoUrl));
  } else {
    // 旧格式：video 为 config 单条
    const config = (m.config || {}) as {
      title?: string;
      description?: string;
      cover_url?: string;
      cover_key?: string;
      video_url?: string;
    };
    if (config.video_url) {
      videos = [
        {
          title: config.title || "舞蹈视频",
          description: config.description || "",
          coverUrl: config.cover_url || config.cover_key || "",
          videoUrl: config.video_url,
        },
      ];
    }
  }

  return videos.length > 0 ? { type: "video", videos } : null;
};

/**
 * 把后端 payload.modules 规范化为页面内部结构：
 * 过滤 notice / enabled=false，按 sort 升序排列，空数据模块直接丢弃。
 */
const normalizeModules = (payload: HomeConfigPayload): HomeModule[] => {
  const rawModules = Array.isArray(payload?.modules) ? payload.modules : [];

  return rawModules
    .filter((m) => Boolean(m) && typeof m.type === "string")
    .filter((m) => m.type !== "notice" && m.enabled !== false)
    .slice()
    .sort((a, b) => (a.sort ?? 0) - (b.sort ?? 0))
    .map((m): HomeModule | null => {
      if (m.type === "banner") return normalizeBanner(m);
      if (m.type === "teachers") return normalizeTeachers(m);
      if (m.type === "courses") return normalizeCourses(m);
      if (m.type === "video") return normalizeVideo(m);
      return null;
    })
    .filter((m): m is HomeModule => m !== null);
};

/** 仅当首页配置包含 teachers 模块时才拉取教师数据 */
const loadTeachersForModules = async () => {
  const module = modules.value.find(
    (m): m is TeachersModule => m.type === "teachers",
  );
  if (!module) {
    teachers.value = [];
    return;
  }

  teachersLoading.value = true;
  try {
    const result = await teacherApi.list();
    if (isUnmounted) return;
    if ((result.code === 0 || result.code === 200) && Array.isArray(result.data)) {
      teachers.value = pickByIds(result.data, module.teacherIds, module.limit);
    }
  } catch (err) {
    console.error("加载教师列表失败:", err);
  } finally {
    if (!isUnmounted) teachersLoading.value = false;
  }
};

/** 仅当首页配置包含 courses 模块时才拉取课程数据 */
const loadCoursesForModules = async () => {
  const module = modules.value.find(
    (m): m is CoursesModule => m.type === "courses",
  );
  if (!module) {
    courses.value = [];
    return;
  }

  loading.value = true;
  try {
    const result = await studentApi.getCourses({});
    if (isUnmounted) return;
    if (result.code === 0 || result.code === 200) {
      const list = extractList<any>(result);
      courses.value = pickByIds(list, module.courseIds, module.limit);
    }
  } catch (err) {
    console.error("课程列表请求异常:", err);
  } finally {
    if (!isUnmounted) loading.value = false;
  }
};

/** 未发布配置 / 请求失败时的默认首页模块（保留原有浏览体验） */
const applyFallbackModules = async () => {
  if (isUnmounted) return;
  modules.value = [
    { type: "banner", banners: DEFAULT_BANNERS },
    { type: "teachers", teacherIds: [], limit: Number.POSITIVE_INFINITY },
    { type: "courses", courseIds: [], limit: 3 },
    { type: "video", videos: DEFAULT_VIDEOS },
  ];
  await Promise.all([loadTeachersForModules(), loadCoursesForModules()]);
};

/** 加载首页配置；失败或 404（未发布）时降级到默认内容 */
const loadHomeConfig = async () => {
  try {
    const result = await homeConfigApi.getPublished();
    if (isUnmounted) return;
    if ((result.code === 0 || result.code === 200) && result.data?.payload) {
      // 已发布配置：完全以后台 sort / enabled 为准（notice 已在规范化阶段丢弃）
      modules.value = normalizeModules(result.data.payload);
      await Promise.all([loadTeachersForModules(), loadCoursesForModules()]);
      return;
    }
    await applyFallbackModules();
  } catch (err) {
    console.warn("首页配置加载失败，使用默认内容降级:", err);
    await applyFallbackModules();
  }
};

const getTeacherSpecialty = (teacher: TeacherListItem) => {
  if (teacher.specialties && teacher.specialties.length > 0) {
    return teacher.specialties[0];
  }
  return teacher.title || "舞蹈教师";
};

const goToTeacherDetail = (id: number) => {
  navigateTo({ url: `/pages/student/teachers/detail?id=${id}` });
};

/** 当前内联播放的视频标识（空串表示全部为封面态） */
const activeVideoKey = ref("");

/** 播放期间锁定首页滚动，避免 scroll-view 滚动与原生视频层不同步 */
const scrollLocked = ref(false);

/** 预签名地址过期后换取的新地址，按视频标识缓存 */
const refreshedVideoUrls = ref<Record<string, string>>({});

/** 已尝试过刷新地址的视频，避免 error 回调重复请求 */
const refreshedVideoKeys = new Set<string>();

const videoKeyOf = (moduleIndex: number, index: number) =>
  `${moduleIndex}-${index}`;

const isVideoActive = (moduleIndex: number, index: number) =>
  activeVideoKey.value === videoKeyOf(moduleIndex, index);

/** 当前应使用的播放地址：优先使用刷新后的地址 */
const getVideoSrc = (
  moduleIndex: number,
  index: number,
  video: VideoView,
): string =>
  refreshedVideoUrls.value[videoKeyOf(moduleIndex, index)] || video.videoUrl;

/** 点击封面：在原卡片内激活原生播放器（同一时刻只保留一个播放器实例） */
const startInlinePlay = (moduleIndex: number, index: number) => {
  activeVideoKey.value = videoKeyOf(moduleIndex, index);
};

/** 从预签名 URL 还原 object_key（路径部分即 t/{tenant}/...） */
const deriveObjectKey = (url: string): string => {
  if (!url) return "";
  const noQuery = url.split("?")[0];
  const idx = noQuery.indexOf("/t/");
  return idx >= 0 ? decodeURIComponent(noQuery.slice(idx + 1)) : "";
};

const onVideoPlay = () => {
  scrollLocked.value = true;
};

const onVideoPause = () => {
  scrollLocked.value = false;
};

const onVideoEnded = () => {
  scrollLocked.value = false;
};

/**
 * 播放失败处理：
 * 1. 预签名地址可能过期，用 object_key 换取新地址重试一次；
 * 2. 仍失败则提示具体 errMsg（域名未校验 / 编码不支持 / 403 等）。
 */
const onVideoError = async (
  e: any,
  video: VideoView,
  moduleIndex: number,
  index: number,
) => {
  const errMsg: string = e?.detail?.errMsg || "未知错误";
  const key = videoKeyOf(moduleIndex, index);
  console.error("❌ 视频播放失败:", errMsg, video.videoUrl);

  if (!refreshedVideoKeys.has(key)) {
    refreshedVideoKeys.add(key);
    const objectKey = video.videoKey || deriveObjectKey(video.videoUrl);
    if (objectKey) {
      try {
        const res = await uploadApi.getUrl(objectKey);
        const newUrl = res.data?.url || "";
        if (newUrl) {
          refreshedVideoUrls.value = {
            ...refreshedVideoUrls.value,
            [key]: newUrl,
          };
          return;
        }
      } catch {
        // 换取失败，走统一错误提示
      }
    }
  }

  uni.showToast({
    title: `视频加载失败：${errMsg}`,
    icon: "none",
    duration: 3000,
  });
};

/** 页面隐藏 / 卸载时移除播放器，避免后台继续播放 */
const stopInlineVideo = () => {
  activeVideoKey.value = "";
  scrollLocked.value = false;
};

onHide(stopInlineVideo);

const goToCourseDetail = (id: number) => {
  navigateTo({ url: `/pages/student/courses/detail?id=${id}` });
};

const goToAllCourses = () => {
  navigateTo({ url: "/pages/student/courses/list" });
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
          // 毛笔行楷 + 大字距，柔和标题不再是默认黑体的生硬感
          font-family: "BannerSerif", "STKaiti", "Kaiti SC", "KaiTi", "楷体",
            serif;
          font-size: 48rpx;
          font-weight: 400;
          letter-spacing: 8rpx;
          color: #fff;
          line-height: 1.35;
          text-shadow: 0 2rpx 6rpx rgba(30, 18, 8, 0.55),
            0 8rpx 28rpx rgba(30, 18, 8, 0.35);
        }

        // 金线 + 菱形装饰，呼应香槟金主题
        .banner-divider {
          display: flex;
          align-items: center;
          gap: 10rpx;
          margin: 16rpx 0 18rpx;

          .divider-line {
            width: 56rpx;
            height: 1rpx;
            background: linear-gradient(
              90deg,
              rgba(217, 185, 138, 0) 0%,
              #d9b98a 100%
            );

            &:last-child {
              background: linear-gradient(
                90deg,
                #d9b98a 0%,
                rgba(217, 185, 138, 0) 100%
              );
            }
          }

          .divider-diamond {
            width: 8rpx;
            height: 8rpx;
            background: #e3c69a;
            transform: rotate(45deg);
          }
        }

        .banner-subtitle {
          display: block;
          font-family: "BannerSerif", "STKaiti", "Kaiti SC", "KaiTi", "楷体",
            serif;
          font-size: 24rpx;
          letter-spacing: 6rpx;
          color: rgba(255, 250, 242, 0.88);
          line-height: 1.6;
          text-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.35);
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
      width: 210rpx;
      flex-shrink: 0;
      padding: 24rpx 16rpx 20rpx;
      box-sizing: border-box;
      background: #ffffff;
      border: 1rpx solid #ebe7e1;
      border-radius: 20rpx;
      box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.03);

      .teacher-avatar {
        width: 132rpx;
        height: 132rpx;
        border-radius: 50%;
        overflow: hidden;
        margin-bottom: 16rpx;

        .avatar-image {
          width: 100%;
          height: 100%;
          display: block;
        }

        .avatar-placeholder {
          position: relative;
          width: 100%;
          height: 100%;
          // 暖香槟色底 + 浅金棕剪影，贴合首页主题
          background: #f4ebdf;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          overflow: hidden;

          // 头部（圆形）
          .avatar-head {
            width: 46rpx;
            height: 46rpx;
            border-radius: 50%;
            background: #d8c3a4;
            margin-bottom: 6rpx;
          }

          // 肩部（圆弧，底部超出裁切形成半身像）
          .avatar-body {
            width: 86rpx;
            height: 60rpx;
            border-radius: 44rpx 44rpx 0 0;
            background: #d8c3a4;
            margin-bottom: -18rpx;
          }
        }
      }

      .teacher-info {
        text-align: center;
        width: 100%;

        .teacher-name {
          display: block;
          font-size: 28rpx;
          font-weight: 600;
          color: #1f1f1f;
          margin-bottom: 6rpx;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .teacher-specialty {
          display: block;
          font-size: 24rpx;
          color: #9b9b9b;
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
  }

  // 舞蹈视频区域（独立模块，直接位于 main-content 下）
  .videos-section {
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
          /* 16:9，与后台视频比例一致，全屏前小窗不留黑边 */
          height: 422rpx;
          overflow: hidden;

          .cover-image {
            width: 100%;
            height: 100%;
            display: block;
          }

          .inline-video {
            width: 100%;
            height: 100%;
            display: block;
            background: #000;
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
</style>
