<template>
  <div class="miniapp-preview">
    <!-- 手机外壳 -->
    <div class="phone-shell">
      <div class="phone-screen">
        <!-- 顶部状态栏 -->
        <div class="status-bar">
          <span>9:41</span>
          <span class="status-icons">
            <el-icon><Connection /></el-icon>
            <el-icon><Monitor /></el-icon>
          </span>
        </div>

        <!-- 自定义导航栏（对齐小程序 AppNavbar：租户名 + 微信胶囊） -->
        <div class="app-navbar">
          <div class="location-selector">
            <span class="location-icon"></span>
            <span class="location-text">{{ tenantName }}</span>
            <span class="location-arrow">▾</span>
          </div>
          <div class="wx-capsule">
            <span class="capsule-dots">•••</span>
            <span class="capsule-divider"></span>
            <span class="capsule-ring"></span>
          </div>
        </div>

        <!-- 内容区域：按草稿 modules 的 sort 升序渲染，仅渲染已启用且有内容的模块 -->
        <div class="app-content">
          <template v-for="m in orderedModules" :key="m.type">
            <!-- Banner 轮播 -->
            <div v-if="m.type === 'banner' && bannerItems.length" class="banner-section">
              <el-carousel
                class="banner-swiper"
                height="180px"
                :interval="4000"
                indicator-position="inside"
                arrow="never"
              >
                <el-carousel-item v-for="(item, i) in bannerItems" :key="i">
                  <div class="banner-slide">
                    <img
                      v-if="imgSrc(item.image_url || item.image_key)"
                      :src="imgSrc(item.image_url || item.image_key)"
                      class="banner-cover-image"
                    />
                    <div v-else class="banner-cover-image banner-cover-empty"></div>
                    <div class="banner-overlay"></div>
                    <div class="banner-content">
                      <span v-if="item.title" class="banner-title">{{ item.title }}</span>
                      <div v-if="item.subtitle" class="banner-divider">
                        <span class="divider-line"></span>
                        <span class="divider-diamond"></span>
                        <span class="divider-line"></span>
                      </div>
                      <span v-if="item.subtitle" class="banner-subtitle">{{ item.subtitle }}</span>
                    </div>
                  </div>
                </el-carousel-item>
              </el-carousel>
            </div>

            <!-- 师资团队 -->
            <div
              v-else-if="m.type === 'teachers' && selectedTeachers.length"
              class="teachers-section"
            >
              <div class="section-header">
                <div class="section-title">
                  <span class="title-icon title-icon-teacher"></span>
                  <span class="title-text">师资团队</span>
                </div>
              </div>
              <div class="teachers-scroll">
                <div class="teachers-list">
                  <div v-for="t in selectedTeachers" :key="t.id" class="teacher-item">
                    <div class="teacher-avatar">
                      <img
                        v-if="imgSrc(t.avatar_url)"
                        :src="imgSrc(t.avatar_url)"
                        class="avatar-image"
                      />
                      <div v-else class="avatar-placeholder">
                        <span class="avatar-head"></span>
                        <span class="avatar-body"></span>
                      </div>
                    </div>
                    <div class="teacher-info">
                      <span class="teacher-name">{{ t.nickname || t.phone || '未知教师' }}</span>
                      <span class="teacher-specialty">舞蹈教师</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 推荐课程 -->
            <div v-else-if="m.type === 'courses' && selectedCourses.length" class="courses-section">
              <div class="section-header">
                <div class="section-title">
                  <span class="title-icon title-icon-course"></span>
                  <span class="title-text">推荐课程</span>
                </div>
                <div class="section-more">
                  <span class="more-text">全部课程</span>
                  <span class="more-arrow">›</span>
                </div>
              </div>
              <div class="course-list">
                <div v-for="c in selectedCourses.slice(0, 3)" :key="c.id" class="course-item">
                  <div class="course-image">
                    <img
                      :src="imgSrc(c.cover_url) || '/default-course-cover.jpg'"
                      class="cover-image"
                    />
                  </div>
                  <div class="course-info">
                    <span class="course-name">{{ c.name }}</span>
                    <span class="course-desc">{{
                      c.description || '能力素质训练是一门新手小白的入门必...'
                    }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 舞蹈视频 -->
            <div v-else-if="m.type === 'video' && videoItems.length" class="videos-section">
              <div class="section-header">
                <div class="section-title">
                  <span class="title-icon title-icon-video"></span>
                  <span class="title-text">舞动 · 让生活更美好</span>
                </div>
              </div>
              <div class="video-list">
                <div v-for="(v, i) in videoItems.slice(0, 3)" :key="i" class="video-card">
                  <div class="video-cover">
                    <img
                      v-if="imgSrc(v.cover_url || v.cover_key)"
                      :src="imgSrc(v.cover_url || v.cover_key)"
                      class="cover-image"
                    />
                    <div v-else class="cover-image video-cover-empty"></div>
                    <div class="video-overlay">
                      <div class="play-button"><span class="play-icon">▶</span></div>
                      <span v-if="v.duration" class="video-duration">{{ v.duration }}</span>
                    </div>
                  </div>
                  <div class="video-info">
                    <span class="video-title">{{ v.title || '舞蹈视频' }}</span>
                    <span v-if="v.description" class="video-desc">{{ v.description }}</span>
                  </div>
                </div>
              </div>
            </div>
          </template>

          <div v-if="optionsLoaded && !hasVisibleModule" class="preview-empty">
            暂无可预览内容，请先配置并启用首页模块
          </div>
        </div>

        <!-- 底部导航栏（对齐小程序 HomeTabBar 四个一级 Tab） -->
        <div class="tab-bar">
          <div class="tab-item active">
            <el-icon><HomeFilled /></el-icon>
            <span class="tab-text">首页</span>
            <span class="tab-indicator"></span>
          </div>
          <div class="tab-item">
            <el-icon><Calendar /></el-icon>
            <span class="tab-text">排期</span>
          </div>
          <div class="tab-item">
            <el-icon><ChatDotRound /></el-icon>
            <span class="tab-text">AI 助手</span>
          </div>
          <div class="tab-item">
            <el-icon><User /></el-icon>
            <span class="tab-text">我的</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  Calendar,
  ChatDotRound,
  Connection,
  HomeFilled,
  Monitor,
  User,
} from '@element-plus/icons-vue'
import { courseApi, userApi } from '@dance-saas/api-client'
import type { Course, HomeConfigModule, User as TenantUser } from '@dance-saas/api-client'
import { previewImageUrl, resolveImageUrlAsync } from '@/utils/image'

const props = defineProps<{
  modules: HomeConfigModule[]
}>()

/** 导航栏租户名（与小程序首页默认展示一致） */
const tenantName = ref('舞蹈艺术培训中心')

/** 已启用模块，按 sort 升序（与小程序运行时渲染顺序一致） */
const orderedModules = computed(() =>
  [...props.modules].filter(m => m.enabled).sort((a, b) => a.sort - b.sort)
)

const bannerModule = computed(() => orderedModules.value.find(m => m.type === 'banner'))
const teachersModule = computed(() => orderedModules.value.find(m => m.type === 'teachers'))
const coursesModule = computed(() => orderedModules.value.find(m => m.type === 'courses'))
const videoModule = computed(() => orderedModules.value.find(m => m.type === 'video'))

const bannerItems = computed<any[]>(() => (bannerModule.value?.items || []) as any[])

/** 视频模块固定使用 items[]，兼容旧草稿单条 config 结构 */
const videoItems = computed<any[]>(() => {
  const m = videoModule.value
  if (!m) return []
  if (Array.isArray(m.items) && m.items.length > 0) return m.items as any[]
  const cfg = (m.config || {}) as any
  return cfg.video_url ? [{ ...cfg }] : []
})

const teacherIds = computed<number[]>(
  () => ((teachersModule.value?.config as any)?.teacher_ids || []) as number[]
)
const courseIds = computed<number[]>(
  () => ((coursesModule.value?.config as any)?.course_ids || []) as number[]
)

/** 教师/课程下拉数据（与编辑抽屉使用同一批接口） */
const teacherList = ref<TenantUser[]>([])
const courseList = ref<Course[]>([])
/** 教师/课程加载完成前不展示“无可预览内容”，避免空态误报 */
const optionsLoaded = ref(false)

/** 按配置里的 ID 顺序回显真实教师/课程 */
const selectedTeachers = computed(() =>
  teacherIds.value
    .map(id => teacherList.value.find(t => t.id === id))
    .filter((t): t is TenantUser => !!t)
)
const selectedCourses = computed(() =>
  courseIds.value.map(id => courseList.value.find(c => c.id === id)).filter((c): c is Course => !!c)
)

const hasVisibleModule = computed(() => {
  return (
    (bannerModule.value?.enabled === true && bannerItems.value.length > 0) ||
    (teachersModule.value?.enabled === true && selectedTeachers.value.length > 0) ||
    (coursesModule.value?.enabled === true && selectedCourses.value.length > 0) ||
    (videoModule.value?.enabled === true && videoItems.value.length > 0)
  )
})

/** object_key → 预签名 URL 的本地缓存（draft 返回的是原始 key，需走 /upload/url 换取） */
const resolvedUrls = ref<Record<string, string>>({})

function imgSrc(value?: string | null): string {
  if (!value) return ''
  return resolvedUrls.value[value] || previewImageUrl(value)
}

async function hydrateImages() {
  const values: string[] = []
  bannerItems.value.forEach(it => {
    const v = it.image_url || it.image_key
    if (v) values.push(v)
  })
  selectedTeachers.value.forEach(t => {
    if (t.avatar_url) values.push(t.avatar_url)
  })
  selectedCourses.value.forEach(c => {
    if (c.cover_url) values.push(c.cover_url)
  })
  videoItems.value.forEach(it => {
    const v = it.cover_url || it.cover_key
    if (v) values.push(v)
  })
  const unique = Array.from(new Set(values.filter(Boolean)))
  if (unique.length === 0) return
  await Promise.all(
    unique.map(async v => {
      const url = await resolveImageUrlAsync(v)
      if (url) resolvedUrls.value[v] = url
    })
  )
  resolvedUrls.value = { ...resolvedUrls.value }
}

watch([() => props.modules, teacherList, courseList], hydrateImages, {
  deep: true,
  immediate: true,
})

async function loadOptions() {
  try {
    const res = await userApi.list({ page_size: 200, role_code: 'teacher' })
    let items = res.data.items || []
    // fallback：role_code 过滤为空时拉全量再按角色过滤（与编辑抽屉口径一致）
    if (items.length === 0) {
      const allRes = await userApi.list({ page_size: 500 })
      items = (allRes.data.items || []).filter(
        u => Array.isArray(u.roles) && u.roles.includes('teacher')
      )
    }
    teacherList.value = items
  } catch (e) {
    console.warn('[MiniAppPreview] 加载教师列表失败', e)
  }

  try {
    const res = await courseApi.list({ page_size: 200 })
    courseList.value = res.data.items || []
  } catch (e) {
    console.warn('[MiniAppPreview] 加载课程列表失败', e)
  } finally {
    optionsLoaded.value = true
  }
}

onMounted(loadOptions)
</script>

<style scoped>
.miniapp-preview {
  display: flex;
  justify-content: center;
  padding: 8px 0;
}

.phone-shell {
  width: 375px;
  height: 667px;
  background: #1a1a1a;
  border-radius: 36px;
  padding: 10px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.phone-screen {
  width: 100%;
  height: 100%;
  /* 与小程序首页 page 背景一致的暖米色渐变 */
  background: linear-gradient(180deg, #faf6f0 0%, #f5ede3 100%);
  border-radius: 26px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.status-bar {
  height: 22px;
  background: #fff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 16px;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.status-icons {
  display: flex;
  gap: 3px;
  font-size: 10px;
}

/* 导航栏：白底 + 租户名 + 微信胶囊 */
.app-navbar {
  height: 44px;
  background: #fff;
  border-bottom: 1px solid #f0ebe3;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  flex-shrink: 0;
}

.location-selector {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.location-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%238b7355'%3E%3Cpath d='M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z'/%3E%3C/svg%3E")
    no-repeat center;
  background-size: contain;
}

.location-text {
  font-size: 14px;
  font-weight: 500;
  color: #3d2e1f;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.location-arrow {
  font-size: 11px;
  color: #8b7355;
  line-height: 1;
}

.wx-capsule {
  width: 87px;
  height: 32px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.6);
  display: flex;
  align-items: center;
  justify-content: space-evenly;
  font-size: 12px;
  color: #333;
  flex-shrink: 0;
}

.capsule-dots {
  letter-spacing: 1px;
}

.capsule-divider {
  width: 1px;
  height: 18px;
  background: rgba(0, 0, 0, 0.12);
}

.capsule-ring {
  width: 14px;
  height: 14px;
  border: 1.5px solid #333;
  border-radius: 50%;
  box-sizing: border-box;
}

.app-content {
  flex: 1;
  overflow-y: auto;
  background: transparent;
}

/* ===== Banner：360rpx=180px，内容居中，标题毛笔行楷 ===== */
.banner-section {
  padding: 0;
  margin-bottom: 0;
}

.banner-swiper {
  width: 100%;
}

.banner-slide {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.banner-cover-image {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

.banner-cover-empty {
  background: linear-gradient(135deg, #2d2418, #1a1612);
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
  padding: 20px 24px;
  z-index: 2;
}

.banner-title {
  display: block;
  font-family: 'BannerSerif', 'STKaiti', 'Kaiti SC', 'KaiTi', '楷体', serif;
  font-size: 24px;
  font-weight: 400;
  letter-spacing: 4px;
  color: #fff;
  line-height: 1.35;
  text-shadow:
    0 1px 3px rgba(30, 18, 8, 0.55),
    0 4px 14px rgba(30, 18, 8, 0.35);
}

.banner-divider {
  display: flex;
  align-items: center;
  gap: 5px;
  margin: 8px 0 9px;
}

.divider-line {
  width: 28px;
  height: 1px;
  background: linear-gradient(90deg, rgba(217, 185, 138, 0), #d9b98a);
}

.divider-line:last-child {
  background: linear-gradient(90deg, #d9b98a, rgba(217, 185, 138, 0));
}

.divider-diamond {
  width: 4px;
  height: 4px;
  background: #e3c69a;
  transform: rotate(45deg);
}

.banner-subtitle {
  display: block;
  font-family: 'BannerSerif', 'STKaiti', 'Kaiti SC', 'KaiTi', '楷体', serif;
  font-size: 12px;
  letter-spacing: 3px;
  color: rgba(255, 255, 255, 0.78);
}

/* 轮播指示点：白 40% / 激活香槟金（对齐小程序 swiper 配置） */
.banner-swiper :deep(.el-carousel__indicator .el-carousel__button) {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.4);
}

.banner-swiper :deep(.el-carousel__indicator.is-active .el-carousel__button) {
  background: #c9a66b;
}

/* ===== 区块标题：40rpx/32rpx 内边距，标题 32rpx ===== */
.teachers-section,
.courses-section,
.videos-section {
  padding: 20px 16px 0;
  margin-bottom: 20px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 4px;
}

.title-icon {
  width: 16px;
  height: 16px;
  background-size: contain;
  background-repeat: no-repeat;
  background-position: center;
}

.title-icon-teacher,
.title-icon-course {
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23c9a66b'%3E%3Cpath d='M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z'/%3E%3C/svg%3E");
}

.title-icon-course {
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23c9a66b'%3E%3Cpath d='M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z'/%3E%3C/svg%3E");
}

.title-icon-video {
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23c9a66b'%3E%3Cpath d='M4 5h12a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V7a2 2 0 012-2zm14 4l4-3v12l-4-3V9z'/%3E%3C/svg%3E");
}

.title-text {
  font-size: 16px;
  font-weight: 600;
  color: #3d2e1f;
}

.section-more {
  display: flex;
  align-items: center;
  gap: 2px;
}

.more-text {
  font-size: 12px;
  color: #8b7355;
}

.more-arrow {
  font-size: 14px;
  color: #8b7355;
  line-height: 1;
}

/* ===== 师资：横向滚动卡片，210rpx=105px ===== */
.teachers-scroll {
  overflow-x: auto;
  overflow-y: hidden;
  /* 隐藏滚动条，模拟小程序 scroll-view */
  scrollbar-width: none;
}

.teachers-scroll::-webkit-scrollbar {
  display: none;
}

.teachers-list {
  display: inline-flex;
  gap: 16px;
  padding-bottom: 12px;
}

.teacher-item {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  width: 105px;
  flex-shrink: 0;
  padding: 12px 8px 10px;
  box-sizing: border-box;
  background: #ffffff;
  border: 1px solid #ebe7e1;
  border-radius: 10px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03);
}

.teacher-avatar {
  width: 66px;
  height: 66px;
  border-radius: 50%;
  overflow: hidden;
  margin-bottom: 8px;
}

.avatar-image {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

.avatar-placeholder {
  position: relative;
  width: 100%;
  height: 100%;
  background: #f4ebdf;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.avatar-head {
  width: 23px;
  height: 23px;
  border-radius: 50%;
  background: #d8c3a4;
  margin-bottom: 3px;
}

.avatar-body {
  width: 43px;
  height: 30px;
  border-radius: 22px 22px 0 0;
  background: #d8c3a4;
  margin-bottom: -9px;
}

.teacher-info {
  text-align: center;
  width: 100%;
}

.teacher-name {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: #1f1f1f;
  margin-bottom: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.teacher-specialty {
  display: block;
  font-size: 12px;
  color: #9b9b9b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ===== 推荐课程：160rpx=80px 封面 ===== */
.course-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.course-item {
  display: flex;
  gap: 16px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.92);
  border-radius: 10px;
  border: 1px solid rgba(201, 166, 107, 0.12);
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04);
}

.course-image {
  width: 80px;
  height: 80px;
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
}

.cover-image {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

.course-info {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 0;
}

.course-name {
  display: block;
  font-size: 15px;
  font-weight: 600;
  color: #3d2e1f;
  margin-bottom: 4px;
}

.course-desc {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  font-size: 12px;
  color: #8b7355;
  line-height: 1.5;
}

/* ===== 舞蹈视频：16:9 封面 422rpx=211px ===== */
.video-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.video-card {
  background: rgba(255, 255, 255, 0.92);
  border-radius: 10px;
  border: 1px solid rgba(201, 166, 107, 0.12);
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04);
  overflow: hidden;
}

.video-cover {
  position: relative;
  width: 100%;
  height: 211px;
  overflow: hidden;
}

.video-cover-empty {
  background: linear-gradient(135deg, #2d2418, #1a1612);
}

.video-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(0, 0, 0, 0.1) 0%, rgba(0, 0, 0, 0.4) 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.play-button {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  background: rgba(201, 166, 107, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 10px rgba(201, 166, 107, 0.4);
}

.play-icon {
  font-size: 18px;
  color: #fff;
  margin-left: 3px;
}

.video-duration {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.9);
  background: rgba(0, 0, 0, 0.5);
  padding: 2px 8px;
  border-radius: 10px;
}

.video-info {
  padding: 16px;
}

.video-title {
  display: block;
  font-size: 15px;
  font-weight: 600;
  color: #3d2e1f;
  margin-bottom: 4px;
}

.video-desc {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  font-size: 12px;
  color: #8b7355;
  line-height: 1.5;
}

.preview-empty {
  padding: 80px 24px;
  text-align: center;
  font-size: 12px;
  color: #9b9b9b;
}

/* ===== 底部 TabBar：12rpx 0 28rpx 内边距 ===== */
.tab-bar {
  display: flex;
  background: #fff;
  border-top: 1px solid #f0ebe3;
  padding: 6px 0 14px;
  flex-shrink: 0;
}

.tab-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  font-size: 11px;
  color: #9b9b9b;
  position: relative;
}

.tab-item .el-icon {
  font-size: 22px;
}

.tab-item.active {
  color: #8b7355;
}

.tab-indicator {
  position: absolute;
  top: -6px;
  width: 20px;
  height: 2px;
  border-radius: 1px;
  background: linear-gradient(90deg, #c9a66b, #e3c69a);
}
</style>
