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

        <!-- 页面标题 header -->
        <div class="app-header">
          <span class="header-title">舞蹈约课</span>
        </div>

        <!-- 内容区域（按 modules 顺序渲染） -->
        <div class="app-content">
          <!-- Banner 轮播 -->
          <template v-if="bannerModule?.enabled && bannerBannerItems.length">
            <div class="section banner-section">
              <el-carousel height="160px" :interval="4000" indicator-position="outside">
                <el-carousel-item v-for="(item, i) in bannerBannerItems" :key="i">
                  <div class="banner-item" :style="{ backgroundImage: `url(${imgSrc(item.image_url || item.image_key)})` }">
                    <div class="banner-overlay">
                      <h3 class="banner-title">{{ item.title }}</h3>
                      <p class="banner-subtitle">{{ item.subtitle }}</p>
                    </div>
                  </div>
                </el-carousel-item>
              </el-carousel>
            </div>
          </template>

          <!-- 师资团队 -->
          <template v-if="teachersModule?.enabled">
            <div class="section teachers-section">
              <div class="section-header">
                <span class="section-title">师资团队</span>
                <span class="section-more">查看更多</span>
              </div>
              <div class="teachers-grid">
                <div v-for="i in (teachersModule.config as any)?.teacher_ids?.length || 4" :key="i" class="teacher-card">
                  <div class="teacher-avatar">
                    <el-icon :size="24"><User /></el-icon>
                  </div>
                  <span class="teacher-name">教师 {{ i }}</span>
                </div>
              </div>
            </div>
          </template>

          <!-- 推荐课程 -->
          <template v-if="coursesModule?.enabled">
            <div class="section courses-section">
              <div class="section-header">
                <span class="section-title">推荐课程</span>
                <span class="section-more">查看更多</span>
              </div>
              <div class="courses-list">
                <div v-for="i in (coursesModule.config as any)?.course_ids?.length || 3" :key="i" class="course-card">
                  <div class="course-cover"></div>
                  <div class="course-info">
                    <span class="course-name">舞蹈课程 {{ i }}</span>
                    <span class="course-meta">60分钟 · 剩余充足</span>
                  </div>
                </div>
              </div>
            </div>
          </template>

          <!-- 舞蹈视频（新结构 items[] / 旧结构 config 单条） -->
          <template v-if="videoModule?.enabled && videoItems.length">
            <div class="section video-section">
              <div class="section-header">
                <span class="section-title">{{ videoItems[0]?.title || '舞蹈视频' }}</span>
              </div>
              <div
                class="video-cover"
                :style="videoCover ? { backgroundImage: `url(${imgSrc(videoCover)})` } : {}"
              >
                <div class="video-play-btn">
                  <el-icon :size="36"><VideoPlay /></el-icon>
                </div>
              </div>
            </div>
          </template>

          <!-- 空态提示 -->
          <div
            v-if="!hasAnyEnabledModule"
            class="empty-state"
          >
            <el-icon :size="48" color="#c0c4cc"><Picture /></el-icon>
            <p>暂无已启用的模块</p>
          </div>
        </div>

        <!-- 底部 Tab -->
        <div class="tab-bar">
          <div class="tab-item active">
            <el-icon><HomeFilled /></el-icon>
            <span>首页</span>
          </div>
          <div class="tab-item">
            <el-icon><Calendar /></el-icon>
            <span>排期</span>
          </div>
          <div class="tab-item">
            <el-icon><ChatDotRound /></el-icon>
            <span>AI</span>
          </div>
          <div class="tab-item">
            <el-icon><User /></el-icon>
            <span>我的</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  Calendar,
  ChatDotRound,
  Connection,
  HomeFilled,
  Monitor,
  Picture,
  User,
  VideoPlay,
} from '@element-plus/icons-vue'
import type { HomeConfigModule } from '@dance-saas/api-client'
import { previewImageUrl, resolveImageUrlAsync } from '@/utils/image'

const props = defineProps<{
  modules: HomeConfigModule[]
}>()

const bannerModule = computed(() => props.modules.find(m => m.type === 'banner'))
const bannerBannerItems = computed<any[]>(() => (bannerModule.value?.items || []) as any[])
const teachersModule = computed(() => props.modules.find(m => m.type === 'teachers'))
const coursesModule = computed(() => props.modules.find(m => m.type === 'courses'))
const videoModule = computed(() => props.modules.find(m => m.type === 'video'))

// 视频模块兼容新（items[]）旧（config 单条）两种结构
const videoItems = computed<any[]>(() => {
  const m = videoModule.value
  if (!m) return []
  if (Array.isArray(m.items) && m.items.length > 0) return m.items as any[]
  const cfg = (m.config || {}) as any
  return cfg.video_url || cfg.cover_url ? [cfg] : []
})
const videoCover = computed(() => videoItems.value[0]?.cover_url || videoItems.value[0]?.cover_key || '')

// object_key → 预签名 URL 的本地缓存（draft 返回的是原始 key，需走 /upload/url 换取）
const resolvedUrls = ref<Record<string, string>>({})

function imgSrc(value?: string | null): string {
  if (!value) return ''
  return resolvedUrls.value[value] || previewImageUrl(value)
}

async function hydrateImages() {
  const values: string[] = []
  bannerBannerItems.value.forEach(it => {
    const v = it.image_url || it.image_key
    if (v) values.push(v)
  })
  videoItems.value.forEach(it => {
    const v = it.cover_url || it.cover_key
    if (v) values.push(v)
  })
  const unique = Array.from(new Set(values))
  if (unique.length === 0) return
  await Promise.all(unique.map(async (v) => {
    const url = await resolveImageUrlAsync(v)
    if (url) resolvedUrls.value[v] = url
  }))
  resolvedUrls.value = { ...resolvedUrls.value }
}

watch(() => props.modules, hydrateImages, { deep: true, immediate: true })

const hasAnyEnabledModule = computed(() => {
  return props.modules.some(m => m.enabled)
})

function truncateText(text: string, maxLen: number) {
  if (!text) return ''
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text
}
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
  background: #f5f5f5;
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
}

.status-icons {
  display: flex;
  gap: 3px;
  font-size: 10px;
}

.app-header {
  height: 44px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: 600;
  font-size: 17px;
}

.app-content {
  flex: 1;
  overflow-y: auto;
  padding: 0;
  background: #f5f5f5;
}

.section {
  margin-bottom: 12px;
  background: #fff;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.section-more {
  font-size: 12px;
  color: #909399;
}

/* Banner */
.banner-section {
  padding: 8px;
  background: transparent;
}

.banner-item {
  width: 100%;
  height: 160px;
  border-radius: 10px;
  background-color: #ddd;
  background-size: cover;
  background-position: center;
  position: relative;
  overflow: hidden;
}

.banner-item:not([style*='backgroundImage']) {
  background: linear-gradient(135deg, #667eea, #764ba2);
}

.banner-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 16px;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.6));
  color: #fff;
}

.banner-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 4px 0;
}

.banner-subtitle {
  font-size: 12px;
  margin: 0;
  opacity: 0.85;
}

/* Teachers */
.teachers-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  padding: 0 12px 12px;
}

.teacher-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.teacher-avatar {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: linear-gradient(135deg, #e0e0e0, #f5f5f5);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #bbb;
}

.teacher-name {
  font-size: 11px;
  color: #606266;
}

/* Courses */
.courses-list {
  padding: 0 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.course-card {
  display: flex;
  gap: 10px;
}

.course-cover {
  width: 90px;
  height: 60px;
  border-radius: 6px;
  background: linear-gradient(135deg, #f093fb, #f5576c);
  flex-shrink: 0;
}

.course-info {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
}

.course-name {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
}

.course-meta {
  font-size: 11px;
  color: #909399;
}

/* Video */
.video-cover {
  height: 180px;
  margin: 0 12px 12px;
  border-radius: 10px;
  background: linear-gradient(135deg, #43cea2, #185a9d);
  background-size: cover;
  background-position: center;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.video-play-btn {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #667eea;
}

/* Empty */
.empty-state {
  padding: 60px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #909399;
  font-size: 14px;
}

/* Tab Bar */
.tab-bar {
  height: 58px;
  background: #fff;
  border-top: 1px solid #eee;
  display: flex;
  padding-bottom: 4px;
}

.tab-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  font-size: 11px;
  color: #909399;
}

.tab-item.active {
  color: #667eea;
}
</style>
