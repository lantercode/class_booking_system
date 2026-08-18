<template>
  <view class="course-page">
    <!-- 自定义导航栏 -->
    <AppNavbar
      title=""
      :show-back="false"
      variant="default">

      <template #left>
        <view>课程列表</view>
      </template>
    </AppNavbar>

    <!-- 主内容区域 -->
    <view class="main-content">
      <!-- 搜索栏 -->
      <view class="search-section">
        <AppInput
          v-model="searchKeyword"
          icon="🔍"
          placeholder="搜索课程名称、老师..."
          variant="default"
          clearable
          @confirm="loadCourses"
        />
      </view>

      <!-- 分类筛选 - 使用统一组件 -->
      <AppFilterTabs
        v-model="activeFilter"
        :tabs="filterTabs"
        @change="handleFilterChange"
      />

      <!-- 课程列表 -->
      <scroll-view
        scroll-y
        class="course-scroll"
        :style="{ height: scrollViewHeight + 'px' }"
        :show-scrollbar="false"
        :refresher-enabled="true"
        :refresher-triggered="refreshing"
        @refresherrefresh="handleRefresh"
      >
        <!-- 加载状态 -->
        <view v-if="loading && courses.length === 0" class="loading-container">
          <AppLoading type="skeleton" />
        </view>

        <!-- 空状态 -->
        <AppEmpty
          v-else-if="!loading && courses.length === 0"
          icon="📚"
          title="暂无课程"
          description="当前分类下还没有课程，试试其他分类吧"
        />

        <!-- 课程卡片列表 -->
        <view v-else class="course-grid">
          <AppCard
            v-for="(course, index) in courses"
            :key="course.id"
            variant="glass"
            padding="none"
            clickable
            class="course-card-wrapper"
            :style="{ animationDelay: `${index * 0.04}s` }"
            @tap="goToCourseDetail(course.id)"
          >
            <view class="course-card">
              <!-- 封面图区域 -->
              <view class="card-cover">
                <image
                  v-if="course.cover_url"
                  :src="course.cover_url"
                  mode="aspectFill"
                  class="cover-image"
                />
                <view v-else class="cover-placeholder">
                  <view class="placeholder-bg-gradient"></view>
                  <view class="placeholder-mesh mesh-1"></view>
                  <view class="placeholder-mesh mesh-2"></view>
                  <view class="placeholder-accent-shape"></view>
                  <view class="placeholder-brand-text">DANCE</view>
                  <view class="placeholder-dot-grid"></view>
                </view>
                
                <view class="cover-overlay"></view>

                <!-- 标签徽章 -->
                <view class="cover-badges">
                  <AppBadge :text="course.category" variant="primary" size="sm" />
                </view>
              </view>

              <!-- 信息区域 -->
              <view class="card-content">
                <!-- 课程名称 -->
                <text class="course-name">{{ course.name }}</text>

                <!-- 元信息 -->
                <view class="course-meta">
                  <AppBadge :text="course.level" variant="default" size="sm" dot />
                  <text class="meta-divider">·</text>
                  <text class="meta-text">{{ course.duration_minutes }}分钟</text>
                </view>

                <!-- 底部操作区 -->
                <view class="card-footer">
                  <view class="footer-left">
                    <text class="teacher-hint">查看详情</text>
                  </view>
                  <view class="footer-right">
                    <text class="arrow-icon">→</text>
                  </view>
                </view>
              </view>
            </view>
          </AppCard>
        </view>

        <!-- 底部安全距离 -->
        <view class="bottom-spacer"></view>
      </scroll-view>
    </view>

    <!-- 底部导航栏 -->
    <StudentTabBar currentRoute="/pages/student/courses/index" />

    <!-- AI 智能助手 -->
    <AiAssistant
      :session-id="'student_' + (userId || 'default')"
    />
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { studentApi } from '@/api'
import { checkLogin } from '@/utils/auth'
import StudentTabBar from '@/components/StudentTabBar.vue'
import AiAssistant from '@/components/AiAssistant.vue'
import { navigateTo } from '@/utils/navigation'
import { extractList } from '@/utils/helpers'
import AppNavbar from '@/components/AppNavbar.vue'
import AppCard from '@/components/AppCard.vue'
import AppInput from '@/components/AppInput.vue'
import AppEmpty from '@/components/AppEmpty.vue'
import AppLoading from '@/components/AppLoading.vue'
import AppBadge from '@/components/AppBadge.vue'
import AppFilterTabs from '@/components/AppFilterTabs.vue'

const searchKeyword = ref('')
const activeFilter = ref('all')
const courses = ref<any[]>([])
const loading = ref(false)
const refreshing = ref(false)
const userId = ref('')

const systemInfo = uni.getSystemInfoSync()
const navbarHeight = systemInfo.statusBarHeight + 44
const tabbarHeight = (100 / 750) * systemInfo.windowWidth
const scrollViewHeight = ref(Math.max(
  systemInfo.windowHeight - navbarHeight - tabbarHeight - 120,
  400
))

// ✅ 新增：防抖定时器（用于搜索）
let searchTimer: ReturnType<typeof setTimeout> | null = null

// ✅ 新增：防抖定时器（用于筛选切换）
let filterDebounceTimer: ReturnType<typeof setTimeout> | null = null

// ✅ 新增：加载锁（防止并发请求）
let isLoadingCourses = false

// ✅ 页面卸载标记
let isUnmounted = false

const filterTabs = [
  { label: '全部', value: 'all' },
  // ✅ 关键修复：使用与后台管理系统完全一致的中文分类值
  // 来源：/apps/admin-web/src/views/courses/index.vue (第18-26行)
  { label: '爵士舞', value: '爵士舞' },
  { label: '街舞', value: '街舞' },
  { label: '中国舞', value: '中国舞' },
  { label: '芭蕾', value: '芭蕾' },
  { label: '拉丁', value: '拉丁' },
  { label: '现代舞', value: '现代舞' },
  { label: '瑜伽', value: '瑜伽' }
]

// ✅ 可选优化：如果需要保持简短显示名但传递正确值，可以使用映射
// const categoryMapping = {
//   'classical': '中国舞',
//   'modern': '现代舞',
//   'jazz': '爵士舞',
//   'yoga': '瑜伽'
// }

onMounted(() => {
  if (!checkLogin('student')) return

  const userInfo = uni.getStorageSync('user_info')
  if (userInfo) {
    try {
      const parsed = JSON.parse(userInfo)
      userId.value = parsed.id || ''
    } catch {}
  }

  loadCourses()
})

onUnmounted(() => {
  isUnmounted = true
  // ✅ 清理所有定时器
  if (searchTimer) clearTimeout(searchTimer)
  if (filterDebounceTimer) clearTimeout(filterDebounceTimer)
})

function handleFilterChange(value: string) {
  console.log('🏷️ [Filter] 切换分类:', activeFilter.value, '→', value)
  
  // ✅ 注意：由于v-model已经更新了activeFilter，这里value一定等于activeFilter.value
  // 所以不需要再判断不相等，直接执行加载逻辑即可
  
  // ✅ 防抖：清除之前的定时器
  if (filterDebounceTimer) {
    clearTimeout(filterDebounceTimer)
  }

  // ✅ 延迟100ms执行（防止快速连续点击）
  filterDebounceTimer = setTimeout(() => {
    console.log('🏷️ [Filter] 执行分类切换，当前值:', activeFilter.value)
    loadCourses()
    filterDebounceTimer = null
  }, 100)
}

async function handleRefresh() {
  refreshing.value = true
  await loadCourses()
  refreshing.value = false
}

const loadCourses = async () => {
  // ✅ 防重复调用：如果正在加载中，跳过（避免并发请求）
  if (isLoadingCourses) {
    console.warn('⚠️ [Courses] loadCourses 正在执行，跳过重复调用')
    return
  }

  // ✅ 加锁
  isLoadingCourses = true
  loading.value = true
  
  try {
    const params: any = {}
    
    // ✅ 搜索关键词
    if (searchKeyword.value) {
      params.keyword = searchKeyword.value
    }
    
    // ✅ 分类筛选（核心修复：确保参数正确传递）
    if (activeFilter.value !== 'all') {
      params.category = activeFilter.value
      console.log('📂 [Courses] 分类筛选参数:', activeFilter.value)
    } else {
      console.log('📂 [Courses] 显示全部分类')
    }

    console.log('=== 📚 课程列表 - 开始加载 ===')
    console.log('请求参数:', params)

    const result = await studentApi.getCourses(params)
    
    // ✅ 页面已卸载，不再更新数据
    if (isUnmounted) return
    
    console.log('=== 📚 课程列表 - API 返回 ===')
    console.log('result.code:', result.code)
    console.log('result.data:', result?.data)

    if (result.code === 0 || result.code === 200) {
      const extractedList = extractList(result)
      
      console.log('✅ 解析成功，课程数量:', extractedList.length)
      
      if (extractedList.length > 0) {
        console.log('\n📋 前3个课程:')
        extractedList.slice(0, 3).forEach((course: any, index: number) => {
          console.log(`[${index + 1}] ${course.name || course.title || '未知课程'} (分类: ${course.category || '未分类'})`)
        })
      }
      
      // ✅ 更新数据
      courses.value = extractedList
      
      console.log('\n✅✅✅ 课程列表已更新！当前显示:', courses.value.length, '门课程')
      
      // 等待Vue渲染完成
      await nextTick()
      console.log('🎯 [Courses] DOM更新完成')
      
    } else {
      console.error('❌ 课程列表API错误:', result.code, result.msg)
      uni.showToast({ 
        title: result.msg || '加载失败', 
        icon: 'none' 
      })
    }
    
  } catch (err: any) {
    console.error('❌ 课程列表请求异常:', err)
    uni.showToast({ 
      title: err.message?.substring(0, 20) || '加载失败,请检查网络', 
      icon: 'none' 
    })
  } finally {
    // ✅ 解锁
    isLoadingCourses = false
    loading.value = false
    console.log('🔓 [Courses] 加载完成，状态已重置')
  }
}

const goToCourseDetail = (id: number) => {
  navigateTo({ url: `/pages/student/courses/detail?id=${id}` })
}
</script>

<style lang="scss" scoped>

.course-page {
  @include page-container;           // ✅ 使用统一的页面容器Mixin
}

.main-content {
  @include main-content;             // ✅ 使用统一的主内容区Mixin
  padding: $space-lg $space-md $space-sm;   // 上边距增大

  // 搜索区域 - 统一背景色设计
  .search-section {
    padding-bottom: $space-md; 
    // background: rgba(255, 255, 255, 0.75);  // ✅ 统一：75%白色背景（与内容区协调）
    position: relative;
    z-index: 10;

    // 底部装饰线（视觉分隔）
    // &::after {
    //   content: '';
    //   position: absolute;
    //   bottom: 0;
    //   left: $space-md;
    //   right: $space-md;
    //   height: 1rpx;
    //   background: linear-gradient(
    //     90deg,
    //     transparent,
    //     $border-light 50%,
    //     transparent
    //   );
    // }
  }

  // 课程列表滚动区域 - 统一背景色（筛选标签已提取为AppFilterTabs组件）
  .course-scroll {
    padding: 0 0;
    padding-bottom: $tabbar-height-safe;
    box-sizing: border-box;
  }

  // 加载容器
  .loading-container {
    padding: $space-xl $space-md;
  }

  // 课程网格布局
  .course-grid {
    display: flex;
    flex-direction: column;
    gap: $space-md;
  }

  // 课程卡片包装器
  .course-card-wrapper {
    animation: cardFadeIn 0.35s cubic-bezier(0.22, 0.61, 0.36, 1) both;
    // box-shadow: $shadow-card;
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

  // 课程卡片内部结构
  .course-card {
    display: flex;
    flex-direction: row;
    height: 280rpx;
    border-radius: $radius-lg;
    overflow: hidden;
    background: $bg-elevated;
  }

  // 封面图区域（左侧）
  .card-cover {
    position: relative;
    width: 320rpx;
    height: 100%;
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
      background: #1A1612;
      overflow: hidden;
    }

    /* 底层渐变 */
    .placeholder-bg-gradient {
      position: absolute;
      inset: 0;
      background:
        radial-gradient(ellipse 300rpx 200rpx at 70% 30%, rgba(201, 166, 107, 0.15) 0%, transparent 60%),
        radial-gradient(ellipse 250rpx 180rpx at 30% 70%, rgba(217, 167, 176, 0.1) 0%, transparent 55%),
        linear-gradient(155deg, #1A1612 0%, #2D2418 35%, #1F1A14 65%, #1A1612 100%);
    }

    /* 渐变网格 */
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
        background: radial-gradient(circle at 40% 40%, rgba(201, 166, 107, 0.25), rgba(201, 166, 107, 0.04));
      }

      &.mesh-2 {
        bottom: -10%;
        left: -10%;
        width: 200rpx;
        height: 200rpx;
        background: radial-gradient(circle at 60% 60%, rgba(217, 167, 176, 0.2), rgba(217, 167, 176, 0.03));
      }
    }

    /* 金色装饰 */
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

    /* 品牌大字 */
    .placeholder-brand-text {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%) rotate(-8deg);
      font-size: 60rpx;
      font-weight: 900;
      color: rgba(201, 166, 107, 0.07);
      letter-spacing: 10rpx;
      white-space: nowrap;
      pointer-events: none;
    }

    /* 圆点网格 */
    .placeholder-dot-grid {
      position: absolute;
      inset: 0;
      background-image: radial-gradient(rgba(201, 166, 107, 0.05) 1rpx, transparent 1rpx);
      background-size: 20rpx 20rpx;
      opacity: 0.4;
    }

    /* 图片遮罩 */
    .cover-overlay {
      position: absolute;
      inset: 0;
      background: linear-gradient(
        180deg,
        rgba(26, 26, 26, 0) 0%,
        rgba(26, 26, 26, 0.04) 70%,
        rgba(26, 26, 26, 0.15) 100%
      );
      pointer-events: none;
    }

    // 徽章标签
    .cover-badges {
      position: absolute;
      top: $space-sm;
      left: $space-sm;
      z-index: 2;
    }
  }

  // 内容区域（右侧）
  .card-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: $space-md;
    overflow: hidden;

    // 课程名称
    .course-name {
      @include text-h4;
      color: $text-primary;
      @include text-clamp(2);
      margin-bottom: $vr-relaxed;
    }

    // 元信息行
    .course-meta {
      display: flex;
      align-items: center;
      gap: $space-2xs;
      margin-bottom: auto;

      .meta-divider {
        color: $text-tertiary;
        font-size: $font-size-caption;
      }

      .meta-text {
        @include text-caption;
        color: $text-tertiary;
      }
    }

    // 底部操作区
    .card-footer {
      @include flex-between;
      align-items: center;
      padding-top: $vr-normal;
      border-top: 1rpx solid $border-light;   // 更新：使用新变量（浅灰边框）

      .teacher-hint {
        @include text-caption;
        color: $primary-solid;
        font-weight: $font-weight-medium;
      }

      .arrow-icon {
        font-size: $font-size-body;
        color: $primary-solid;
        transition: transform $duration-fast $ease-standard;
      }

      &:hover .arrow-icon,
      &:active .arrow-icon {
        transform: translateX(4rpx);
      }
    }
  }

  // 底部安全间距
  .bottom-spacer {
    height: $space-lg;
  }
}

// 响应式：小屏设备适配
@include respond-to(small) {
  .course-card {
    flex-direction: column !important;
    height: auto !important;
  }

  .card-cover {
    width: 100% !important;
    height: 300rpx !important;

    .cover-overlay {
      background: linear-gradient(
        180deg,
        rgba(26, 26, 26, 0) 0%,
        rgba(26, 26, 26, 0.04) 70%,
        rgba(26, 26, 26, 0.15) 100%
      );
    }
  }
}
</style>