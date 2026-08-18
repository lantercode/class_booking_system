<template>
  <view class="course-detail-page">

    <!-- 封面区域 -->
    <view class="hero-section">
      <view class="hero-background">
        <image
          v-if="course.cover_url"
          :src="course.cover_url"
          mode="aspectFill"
          class="hero-image"
        />
        <view v-else class="hero-placeholder">
          <view class="hero-bg-gradient"></view>
          <view class="hero-mesh mesh-1"></view>
          <view class="hero-mesh mesh-2"></view>
          <view class="hero-mesh mesh-3"></view>
          <view class="hero-accent-shape"></view>
          <view class="hero-gold-line"></view>
          <view class="hero-brand-text">DANCE</view>
          <view class="hero-dot-grid"></view>
        </view>

        <view class="hero-overlay"></view>
      </view>

      <view class="hero-content">
        <AppBadge :text="course.category" variant="primary" size="lg" />
        <text class="course-title">{{ course.name }}</text>
        <view class="course-tags">
          <AppBadge :text="course.level" variant="default" size="sm" dot />
          <text class="tag-divider">·</text>
          <text class="tag-text">{{ course.duration_minutes }}分钟</text>
        </view>
      </view>
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
      <!-- 数据统计卡片 -->
      <AppCard variant="glass" padding="lg" class="stats-card">
        <view class="stats-grid">
          <view class="stat-item">
            <text class="stat-value">{{ course.duration_minutes }}</text>
            <text class="stat-label">分钟</text>
          </view>
          <view class="stat-divider"></view>
          <view class="stat-item">
            <text class="stat-value">{{ course.category }}</text>
            <text class="stat-label">分类</text>
          </view>
          <view class="stat-divider"></view>
          <view class="stat-item">
            <text class="stat-value">{{ course.level }}</text>
            <text class="stat-label">级别</text>
          </view>
        </view>
      </AppCard>

      <!-- 课程简介卡片 -->
      <AppCard variant="elevated" padding="lg" class="info-card">
        <view class="card-header-custom">
          <text class="card-title-custom">📖 课程简介</text>
        </view>
        <view class="card-body-custom">
          <text class="description-text">{{ course.description || '暂无介绍' }}</text>
        </view>
      </AppCard>

      <!-- 近期排期 -->
      <view class="schedule-section">
        <view class="section-header">
          <text class="section-title">📅 近期排期</text>
          <view v-if="schedules.length > 0" class="schedule-count">
            <AppBadge :text="`${schedules.length}个排期`" variant="default" size="sm" />
          </view>
        </view>

        <AppEmpty
          v-if="!loading && schedules.length === 0"
          icon="📭"
          title="暂无排期"
          description="该课程暂未安排上课时间"
          :padding="true"
        />

        <view v-else class="schedule-list">
          <view
            v-for="(schedule, index) in displaySchedules"
            :key="schedule._key"
            class="schedule-card"
            :style="{ animationDelay: `${index * 0.04}s` }"
          >
            <!-- 第一行：日期 + 时间 + 状态 -->
            <view class="card-row">
              <view class="date-time-group">
                <text class="date-text">{{ schedule._dateText }}</text>
                <text class="dot-sep">·</text>
                <text class="time-text">{{ schedule._startTime }} — {{ schedule._endTime }}</text>
              </view>
              <view class="status-tag" :class="schedule._statusClass">
                <text>{{ schedule._statusText }}</text>
              </view>
            </view>

            <!-- 第二行：教室 + 老师 -->
            <view class="card-row card-row--info">
              <text class="info-text">
                <text class="info-icon">📍</text>{{ schedule.classroom_name || '未安排教室' }}
              </text>
              <text class="info-divider">·</text>
              <text class="info-text">
                <text class="info-icon">👨‍🏫</text>{{ schedule.teacher_name || '未知' }}
              </text>
            </view>

            <!-- 第三行：容量进度条 + 按钮 -->
            <view class="card-row card-row--action">
              <view class="capacity-group">
                <view class="capacity-bar">
                  <view
                    class="capacity-fill"
                    :class="{ full: schedule._isFull }"
                    :style="{ width: schedule._capacityPercent + '%' }"
                  ></view>
                </view>
                <text class="capacity-label">{{ schedule.booked_count }}/{{ schedule.capacity }}</text>
              </view>
              <button
                class="book-btn"
                :class="{
                  disabled: schedule._isDisabled,
                  booked: schedule._isBooked
                }"
                :disabled="schedule._isDisabled"
                :loading="bookingLoading[schedule.id]"
                @tap="handleBooking(schedule.id, schedule._isBooked)"
              >
                {{ schedule._btnText }}
              </button>
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

    <!-- AI 智能助手 -->
    <AiAssistant
      :session-id="'student_' + (userId || 'default')"
    />
  </view>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { courseApi, scheduleApi, bookingApi } from '@/api'
import { formatDate, formatTime } from '@/utils/date'
import { extractList } from '@/utils/helpers'
import AiAssistant from '@/components/AiAssistant.vue'

const courseId = ref(0)
const userId = ref('')
const course = ref<any>({})
const schedules = ref<any[]>([])
const myBookings = ref<any[]>([])
const loading = ref(false)
const refreshing = ref(false)
const bookingLoading = reactive<Record<number, boolean>>({})

const systemInfo = uni.getSystemInfoSync()
const heroHeightPx = (520 / 750) * systemInfo.windowWidth
const scrollViewHeight = ref(Math.max(systemInfo.windowHeight - heroHeightPx, 400))

// ✅ 页面卸载标记
let isUnmounted = false

// ✅ 企业级优化：Computed预处理所有显示数据（参照排期页面）
const displaySchedules = computed(() => {
  const bookedScheduleIds = new Set(
    myBookings.value.map((b: any) => b.schedule_id)
  )

  return schedules.value.map((schedule: any, index: number) => {
    const isBooked = bookedScheduleIds.has(schedule.id)
    const isFull = schedule.booked_count >= schedule.capacity

    return {
      ...schedule,

      _key: schedule.id || `schedule-${index}`,
      _dateText: formatDate(schedule.start_at, true),
      _startTime: formatTime(schedule.start_at),
      _endTime: formatTime(schedule.end_at),

      _isBooked: isBooked,
      _isFull: isFull,
      _isDisabled: isFull && !isBooked,
      _capacityPercent: schedule.capacity > 0
        ? Math.min(Math.round((schedule.booked_count / schedule.capacity) * 100), 100)
        : 0,

      _statusClass: isBooked ? 'booked' : (isFull ? 'full' : 'available'),
      _statusText: isBooked ? '已预约' : (isFull ? '已满' : '可预约'),
      _btnText: isBooked ? '取消' : (isFull ? '已满' : '预约')
    }
  })
})

onUnmounted(() => {
  isUnmounted = true
})

onMounted(() => {
  console.log('=== 📚 课程详情页 - 开始初始化 ===')

  const userInfo = uni.getStorageSync('user_info')
  if (userInfo) {
    try {
      const parsed = JSON.parse(userInfo)
      userId.value = parsed.id || ''
    } catch {}
  }

  // ✅ 多种方式尝试获取课程ID（增强兼容性）
  let id: number | null = null

  try {
    const pages = getCurrentPages()
    console.log("pages", pages)
    if (pages.length > 0) {
      const currentPage = pages[pages.length - 1] as any
      const options = currentPage?.options || {}

      console.log('📋 页面参数:', options)

      // 方式1：从options获取
      if (options.id) {
        id = parseInt(options.id)
        console.log('✅ 从options获取到ID:', id)
      }

      // 方式2：从页面实例获取（某些真机环境）
      if (!id && currentPage?.id) {
        id = parseInt(currentPage.id)
        console.log('✅ 从页面实例获取到ID:', id)
      }
    }
  } catch (error) {
    console.error('❌ 获取页面参数失败:', error)
  }

  // ✅ 如果还是获取不到，尝试从URL解析
  if (!id) {
    try {
      const currentPages = getCurrentPages()
      const currentRoute = currentPages[currentPages.length - 1]?.route || ''
      const urlMatch = currentRoute.match(/id=(\d+)/)

      if (urlMatch && urlMatch[1]) {
        id = parseInt(urlMatch[1])
        console.log('✅ 从URL解析获取到ID:', id)
      }
    } catch (error) {
      console.warn('⚠️ URL解析失败:', error)
    }
  }

  if (id && id > 0) {
    courseId.value = id
    console.log('🎯 最终使用课程ID:', courseId.value)
    loadInitialData()
  } else {
    console.error('❌ 无法获取课程ID！')
    uni.showModal({
      title: '错误',
      content: '缺少课程ID参数，请返回重试',
      showCancel: false,
      success: () => {
        uni.navigateBack({
          fail: () => {
            uni.reLaunch({ url: '/pages/student/courses/index' })
          }
        })
      }
    })
  }
})

const loadInitialData = async () => {
  loading.value = true
  console.log('⏳ [Detail] 开始加载课程详情数据...')

  try {
    // ✅ 关键优化：先加载课程基本信息（核心数据）
    console.log('📖 [Detail] Step 1: 加载课程信息...')
    await loadCourse()

    // ✅ 页面已卸载，不再更新数据
    if (isUnmounted) return

    if (!course.value || !course.value.id) {
      throw new Error('课程信息加载失败或数据为空')
    }

    console.log('✅ [Detail] 课程信息已加载:', course.value.name)

    // ✅ 然后并行加载辅助数据（排期+预约）
    console.log('📅 [Detail] Step 2: 并行加载排期和预约...')
    await Promise.all([
      loadSchedules(),
      loadMyBookings()
    ])

    // ✅ 页面已卸载，不再更新数据
    if (isUnmounted) return

    console.log('✅✅✅ [Detail] 所有数据加载完成！')

  } catch (error) {
    console.error('❌ [Detail] 数据加载失败:', error)
    uni.showToast({
      title: '加载数据失败',
      icon: 'none',
      duration: 2000
    })
  } finally {
    loading.value = false
    console.log('🔓 [Detail] Loading状态已释放')
  }
}

const handleRefresh = async () => {
  refreshing.value = true
  try {
    await Promise.all([
      loadCourse(),
      loadSchedules(),
      loadMyBookings()
    ])
  } finally {
    refreshing.value = false
  }
}

const loadCourse = async () => {
  try {
    console.log(`🌐 [Detail] 请求课程API: ID=${courseId.value}`)
    const result = await courseApi.get(courseId.value)

    console.log('📦 [Detail] API返回:', {
      code: result?.code,
      hasData: !!result?.data,
      dataKeys: result?.data ? Object.keys(result.data) : []
    })

    if (result?.code === 0 || result?.code === 200) {
      if (result?.data && typeof result.data === 'object') {
        course.value = result.data
        console.log('✅ [Detail] 课程数据赋值成功:', {
          id: course.value.id,
          name: course.value.name,
          category: course.value.category
        })
      } else {
        throw new Error('返回数据格式异常')
      }
    } else {
      throw new Error(result?.msg || `API返回错误码: ${result?.code}`)
    }

  } catch (error) {
    console.error('❌ [Detail] loadCourse失败:', error)
    throw error  // 向上抛出，由loadInitialData统一处理
  }
}

const loadSchedules = async () => {
  try {
    console.log('📅 [Detail] 开始加载排期列表...')
    console.log(`📅 [Detail] 请求参数: course_id=${courseId.value}, status=1`)

    const result = await scheduleApi.list({
      course_id: courseId.value,
      status: 1  // 1=进行中/可预约的排期
    })

    // ✅ 页面已卸载，不再更新数据
    if (isUnmounted) return

    console.log('📦 [Detail] 排期API返回:', {
      code: result?.code,
      hasData: !!result?.data,
      dataType: typeof result?.data,
      isArray: Array.isArray(result?.data)
    })

    // ✅ 关键修复：多格式兼容（与loadMyBookings保持一致）
    const responseData = result?.data as any

    let finalList: any[] = []

    // 格式1: { data: { items: [...] } } - 标准分页结构
    if (responseData?.items && Array.isArray(responseData.items)) {
      finalList = responseData.items
      console.log(`✅ [Detail] 从 data.items 提取排期: ${finalList.length} 条`)
    }
    // 格式2: { data: [...] } - 直接数组
    else if (Array.isArray(responseData)) {
      finalList = responseData
      console.log(`✅ [Detail] 从 data数组提取排期: ${finalList.length} 条`)
    }
    // 格式3: 其他结构，使用extractList工具函数
    else {
      finalList = extractList(result)
      console.log(`✅ [Detail] 使用 extractList 提取排期: ${finalList.length} 条`)
    }

    // ✅ 数据校验和日志
    schedules.value = finalList

    console.log('📋 [Detail] 排期列表详情:', schedules.value)
    // finalList.slice(0, 3).forEach((schedule, index) => {
    //   console.log(`  [${index + 1}] ID:${schedule.id}, 时间:${schedule.start_at}, 教室:${schedule.classroom_name}`)
    // })

    // if (finalList.length > 3) {
    //   console.log(`  ... 共 ${finalList.length} 条记录`)
    // }

    // if (finalList.length === 0) {
    //   console.log('⚠️ [Detail] 该课程暂无可用排期')
    // }

  } catch (error) {
    console.error('❌ [Detail] loadSchedules失败:', error)
    uni.showToast({
      title: '加载排期失败',
      icon: 'none',
      duration: 2000
    })

    // ✅ 确保出错时也有空数组，避免渲染错误
    schedules.value = []
  }
}

const loadMyBookings = async () => {
  try {
    console.log('=== 课程详情页 - 加载我的预约 ===')
    const result = await bookingApi.list({ status: 1 })

    // ✅ 页面已卸载，不再更新数据
    if (isUnmounted) return

    const responseData = result?.data as any

    let finalList: any[] = []

    if (responseData?.items && Array.isArray(responseData.items)) {
      finalList = responseData.items
    } else if (Array.isArray(responseData)) {
      finalList = responseData
    } else {
      finalList = extractList(result)
    }

    myBookings.value = finalList

    console.log('✅ 课程详情页 - 已加载预约记录:', myBookings.value.length, '条')
  } catch (error) {
    console.error('❌ 课程详情页 - 加载预约失败:', error)
    uni.showToast({ title: '加载预约失败', icon: 'none' })
  }
}

const handleBooking = async (scheduleId: number, alreadyBooked: boolean = false) => {
  if (alreadyBooked) {
    uni.showModal({
      title: '取消预约',
      content: '确定要取消此预约吗？取消后其他学员可以预约该名额。',
      confirmColor: '#e53935',
      success: async (res) => {
        if (res.confirm) {
          await cancelBooking(scheduleId)
        }
      }
    })
    return
  }

  uni.showModal({
    title: '确认预约',
    content: '确定要预约此课程吗？预约成功后将收到提醒通知。',
    confirmColor: '#667eea',
    success: async (res) => {
      if (res.confirm) {
        await createBooking(scheduleId)
      }
    }
  })
}

const createBooking = async (scheduleId: number) => {
  bookingLoading[scheduleId] = true
  try {
    const result = await bookingApi.create({ schedule_id: scheduleId })
    if (result.code === 0 || result.code === 200) {
      uni.showToast({
        title: '✨ 预约成功',
        icon: 'success',
        duration: 2000
      })
      await Promise.all([loadSchedules(), loadMyBookings()])
    } else {
      uni.showToast({ title: result.msg || '预约失败', icon: 'none' })
    }
  } catch (error: any) {
    uni.showToast({ title: error.msg || '预约失败', icon: 'none' })
  } finally {
    bookingLoading[scheduleId] = false
  }
}

const cancelBooking = async (scheduleId: number) => {
  bookingLoading[scheduleId] = true
  try {
    const booking = myBookings.value.find(b => b.schedule_id === scheduleId)
    if (!booking) {
      uni.showToast({ title: '未找到预约记录', icon: 'none' })
      return
    }
    const result = await bookingApi.cancel(booking.id)
    if (result.code === 0 || result.code === 200) {
      uni.showToast({
        title: '已取消预约',
        icon: 'success',
        duration: 2000
      })
      await Promise.all([loadSchedules(), loadMyBookings()])
    } else {
      uni.showToast({ title: result.msg || '取消失败', icon: 'none' })
    }
  } catch (error: any) {
    uni.showToast({ title: error.msg || '取消失败', icon: 'none' })
  } finally {
    bookingLoading[scheduleId] = false
  }
}
</script>

<style lang="scss">

.course-detail-page {
  @include page-container($bg-elevated);
}

/* ========== Hero 封面区域 ========== */
.hero-section {
  position: relative;
  height: 520rpx;
  flex-shrink: 0;
  overflow: hidden;
}

.hero-background {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
}

.hero-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* 无图片时的占位背景 - 舞蹈海报风格 */
.hero-placeholder {
  width: 100%;
  height: 100%;
  background: #1A1612;
  position: relative;
  overflow: hidden;
}

/* 底层渐变 - 光影层次 */
.hero-bg-gradient {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 600rpx 400rpx at 70% 30%, rgba(201, 166, 107, 0.18) 0%, transparent 60%),
    radial-gradient(ellipse 500rpx 350rpx at 30% 70%, rgba(217, 167, 176, 0.13) 0%, transparent 55%),
    linear-gradient(155deg, #1A1612 0%, #2D2418 35%, #1F1A14 65%, #1A1612 100%);
}

/* 渐变网格 - 模拟舞池灯光 */
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
    background: radial-gradient(circle at 40% 40%, rgba(201, 166, 107, 0.3), rgba(201, 166, 107, 0.05));
  }

  &.mesh-2 {
    bottom: -15%;
    left: -15%;
    width: 450rpx;
    height: 450rpx;
    background: radial-gradient(circle at 60% 60%, rgba(217, 167, 176, 0.25), rgba(217, 167, 176, 0.04));
  }

  &.mesh-3 {
    top: 40%;
    left: 50%;
    width: 300rpx;
    height: 300rpx;
    background: radial-gradient(circle at 50% 50%, rgba(232, 213, 183, 0.2), transparent);
    transform: translate(-50%, -50%);
  }
}

/* 金色装饰形状 */
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

/* 金色装饰线 */
.hero-gold-line {
  position: absolute;
  top: 28%;
  right: 14%;
  width: 120rpx;
  height: 2rpx;
  background: linear-gradient(90deg, transparent, rgba(201, 166, 107, 0.5), transparent);
  transform: rotate(-20deg);
}

/* 品牌大字 */
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

/* 圆点网格 */
.hero-dot-grid {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(rgba(201, 166, 107, 0.06) 1rpx, transparent 1rpx);
  background-size: 28rpx 28rpx;
  opacity: 0.5;
}

/* 渐变遮罩层 */
.hero-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(
    180deg,
    rgba(26, 26, 26, 0.02) 0%,
    rgba(26, 26, 26, 0.08) 50%,
    rgba(26, 26, 26, 0.3) 80%,
    rgba(26, 26, 26, 0.55) 100%
  );
}

.hero-content {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 40rpx $space-xl $space-xl;
  z-index: 2;
}

.course-title {
  display: block;
  @include font-style($font-size-h2, $font-weight-bold);
  color: #ffffff;
  margin-top: $space-md;
  line-height: 1.3;
  text-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.3);
}

.course-tags {
  display: flex;
  align-items: center;
  gap: $space-sm;
  margin-top: $space-md;
}

.tag-divider {
  color: rgba(255, 255, 255, 0.6);
  font-size: $font-size-caption;
}

.tag-text {
  font-size: $font-size-caption;
  color: rgba(255, 255, 255, 0.9);
}

/* ========== 主内容区域 ========== */
.scroll-wrapper {
  @include main-content;
}

.details-content {
  flex: 1;
  padding: $space-lg $space-md;
  padding-bottom: calc($space-xl + env(safe-area-inset-bottom));
  box-sizing: border-box;
}

/* ========== 统计卡片 ========== */
.stats-card {
  margin-bottom: $space-lg;
  animation: fadeInUp 0.4s ease-out;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: $space-md;
  align-items: center;
}

.stat-item {
  text-align: center;
  padding: $space-md 0;
}

.stat-value {
  display: block;
  @include font-style($font-size-h3, $font-weight-bold);
  color: $primary-solid;
  margin-bottom: $space-xs;
}

.stat-label {
  display: block;
  font-size: $font-size-caption;
  color: $text-secondary;
}

.stat-divider {
  width: 1rpx;
  height: 60rpx;
  background: $border-light;
}

/* ========== 信息卡片通用样式 ========== */
.info-card {
  margin-bottom: $space-lg;
  animation: fadeInUp 0.5s ease-out;
}

.card-header-custom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: $space-lg;
}

.card-title-custom {
  @include font-style($font-size-h4, $font-weight-semibold);
  color: $text-primary;
}

.card-body-custom {
  padding-bottom: $space-sm;
}

/* ========== 课程简介 ========== */
.description-text {
  @include font-style($font-size-body, $font-weight-normal, $line-height-relaxed);
  color: $text-secondary;
  line-height: 1.8;
}

/* ========== 排期区域 ========== */
.schedule-section {
  margin-bottom: $space-lg;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: $space-lg;
}

.section-title {
  @include font-style($font-size-h4, $font-weight-semibold);
  color: $text-primary;
}

.schedule-count {
  display: flex;
  align-items: center;
}

.schedule-list {
  display: flex;
  flex-direction: column;
  gap: $space-md;
}

/* ========== 排期卡片 ========== */
.schedule-card {
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20rpx);
  -webkit-backdrop-filter: blur(20rpx);
  border-radius: $radius-lg;
  border: 1rpx solid $border-subtle;
  padding: $space-md $space-lg;
  box-shadow: $shadow-card;
  transition: transform $duration-fast $ease-standard,
              box-shadow $duration-fast $ease-standard;
  animation: cardFadeIn 0.35s cubic-bezier(0.22, 0.61, 0.36, 1) both;

  &:active {
    transform: translateY(-2rpx);
    box-shadow: $shadow-card-hover;
  }
}

.card-row {
  display: flex;
  align-items: center;
  justify-content: space-between;

  & + & {
    margin-top: $space-sm;
  }
}

.card-row--info {
  justify-content: flex-start;
}

.card-row--action {
  justify-content: space-between;
}

/* 日期 + 时间 */
.date-time-group {
  display: flex;
  align-items: baseline;
  flex: 1;
  min-width: 0;
}

.date-text {
  font-size: $font-size-body;
  font-weight: $font-weight-semibold;
  color: $text-primary;
  flex-shrink: 0;
}

.dot-sep {
  margin: 0 $space-xs;
  color: $text-tertiary;
  font-weight: $font-weight-bold;
}

.time-text {
  font-size: $font-size-body;
  font-weight: $font-weight-medium;
  color: $primary-solid;
}

/* 状态标签 */
.status-tag {
  padding: 2rpx 12rpx;
  border-radius: $radius-full;
  font-size: 20rpx;
  font-weight: $font-weight-medium;
  flex-shrink: 0;
  margin-left: $space-sm;

  &.booked {
    background: $primary-bg;
    color: $primary-solid;
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

/* 信息行 */
.info-text {
  font-size: $font-size-body-sm;
  color: $text-secondary;
  white-space: nowrap;
}

.info-icon {
  margin-right: 2rpx;
}

.info-divider {
  margin: 0 $space-sm;
  color: $text-tertiary;
  font-weight: $font-weight-bold;
}

/* 容量进度条 */
.capacity-group {
  display: flex;
  align-items: center;
  gap: $space-sm;
  flex: 1;
  min-width: 0;
}

.capacity-bar {
  width: 160rpx;
  height: 8rpx;
  background: $bg-secondary;
  border-radius: $radius-full;
  overflow: hidden;
  flex-shrink: 0;
}

.capacity-fill {
  height: 100%;
  background: $primary-solid;
  border-radius: $radius-full;
  transition: width 0.3s ease;

  &.full {
    background: $error-color;
  }
}

.capacity-label {
  font-size: $font-size-caption;
  color: $text-tertiary;
  flex-shrink: 0;
}

/* 预约按钮 */
.book-btn {
  padding: 6rpx $space-xl;
  border-radius: $radius-full;
  font-size: $font-size-body-sm;
  font-weight: $font-weight-semibold;
  background: $primary-gradient;
  color: #fff;
  border: none;
  line-height: 1.5;
  flex-shrink: 0;
  margin-left: auto;
  box-shadow: $shadow-button;

  &:active {
    transform: scale(0.95);
  }

  &.disabled {
    background: $bg-tertiary;
    color: $text-tertiary;
  }

  &.booked {
    background: $error-bg;
    color: $error-color;
  }
}

/* ========== 底部安全距离 ========== */
.bottom-spacer {
  height: calc($space-xl + 80rpx);
}

/* ========== 加载遮罩 ========== */
.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
}

/* ========== 动画关键帧 ========== */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30rpx);
  }
  to {
    opacity: 1;
    transform: translateY(0);
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

@keyframes slideInRight {
  from {
    opacity: 0;
    transform: translateX(40rpx);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
</style>