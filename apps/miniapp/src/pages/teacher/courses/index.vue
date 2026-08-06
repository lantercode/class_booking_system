<template>
  <view class="container">
    <view class="header">
      <text class="header-title">我的课程</text>
      <button class="add-btn" @tap="goToCreate">
        <text class="add-icon">+</text>
        <text>创建课程</text>
      </button>
    </view>

    <view class="search-bar">
      <view class="search-input-wrapper">
        <text class="search-icon">🔍</text>
        <input
          v-model="searchKeyword"
          type="text"
          placeholder="搜索课程名称"
          class="search-input"
          @confirm="loadCourses"
        />
      </view>
    </view>

    <view class="filter-tabs">
      <view
        v-for="tab in filterTabs"
        :key="tab.value"
        class="filter-tab"
        :class="{ active: activeFilter === tab.value }"
        @tap="activeFilter = tab.value; loadCourses()"
      >
        <text>{{ tab.label }}</text>
      </view>
    </view>

    <scroll-view scroll-y class="course-list" :show-scrollbar="false">
      <view v-if="courses.length === 0" class="empty-state">
        <text class="empty-icon">📚</text>
        <text class="empty-text">暂无课程</text>
        <button class="empty-btn" @tap="goToCreate">立即创建</button>
      </view>

      <view
        v-for="course in courses"
        :key="course.id"
        class="course-card"
      >
        <view class="course-cover">
          <image v-if="course.cover_url" :src="course.cover_url" mode="aspectFill" class="cover-image" />
          <view v-else class="cover-placeholder">
            <text class="placeholder-icon">🎭</text>
          </view>
          <view class="course-status" :class="course.status === 1 ? 'active' : 'inactive'">
            <text>{{ course.status === 1 ? '上架中' : '已下架' }}</text>
          </view>
        </view>

        <view class="course-info">
          <text class="course-name">{{ course.name }}</text>
          <view class="course-meta">
            <text class="meta-item">🕐 {{ course.duration_minutes }}分钟</text>
            <text class="meta-item">👥 {{ course.max_capacity }}人</text>
          </view>
          <view class="course-meta">
            <text class="meta-item" v-if="course.category">{{ course.category }}</text>
            <text class="meta-item" v-if="course.level">{{ course.level }}</text>
          </view>
          <!-- <view class="course-price" v-if="false">
            <text class="price-label">¥</text>
            <text class="price-value">{{ course.price || 0 }}</text>
          </view> -->
        </view>

        <view class="course-actions">
          <view class="action-btn edit" @tap="editCourse(course.id)">
            <text>编辑</text>
          </view>
          <view class="action-btn delete" @tap="deleteCourse(course.id)">
            <text>删除</text>
          </view>
        </view>
      </view>
    </scroll-view>

    <TeacherTabBar currentRoute="/pages/teacher/courses/index" />
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { teacherApi, courseApi } from '@/api'
import { checkLogin } from '@/utils/auth'
import TeacherTabBar from '@/components/TeacherTabBar.vue'
import { extractList } from '@/utils/helpers'

const searchKeyword = ref('')
const activeFilter = ref('all')
const courses = ref<any[]>([])

const filterTabs = [
  { label: '全部', value: 'all' },
  { label: '上架', value: 'active' },
  { label: '下架', value: 'inactive' }
]

onMounted(() => {
  if (!checkLogin('teacher')) return
  loadCourses()
})

const loadCourses = async () => {
  try {
    const params: any = {}
    if (searchKeyword.value) params.keyword = searchKeyword.value
    if (activeFilter.value !== 'all') params.status = activeFilter.value === 'active' ? 1 : 0

    const result = await teacherApi.getCourses(params)
    courses.value = extractList(result)
  } catch {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}

const goToCreate = () => {
  uni.navigateTo({ url: '/pages/teacher/courses/form' })
}

const editCourse = (id: number) => {
  uni.navigateTo({ url: `/pages/teacher/courses/form?id=${id}` })
}

const deleteCourse = async (id: number) => {
  uni.showModal({
    title: '确认删除',
    content: '删除后将无法恢复，确定要删除吗？',
    success: async (res) => {
      if (res.confirm) {
        try {
          const result = await courseApi.delete(id)
          if (result.code === 0 || result.code === 200) {
            uni.showToast({ title: '删除成功', icon: 'success' })
            loadCourses()
          } else {
            uni.showToast({ title: result.msg || '删除失败', icon: 'none' })
          }
        } catch {
          uni.showToast({ title: '删除失败', icon: 'none' })
        }
      }
    }
  })
}

const goToSchedule = () => {
  uni.navigateTo({ url: '/pages/teacher/schedule/index' })
}

const goToStudents = () => {
  uni.navigateTo({ url: '/pages/teacher/students/index' })
}

const goToProfile = () => {
  uni.navigateTo({ url: '/pages/teacher/profile/index' })
}
</script>

<style lang="scss">
/* ✅ 已通过 vite.config.ts 全局注入 scrollbar 样式 */
.container {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 120rpx;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 60rpx 32rpx 24rpx;
  background: #fff;
}

.header-title {
  font-size: 36rpx;
  font-weight: bold;
}

.add-btn {
  display: flex;
  align-items: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 40rpx;
  padding: 16rpx 28rpx;
  color: #fff;
  font-size: 26rpx;
}

.add-icon {
  font-size: 32rpx;
  margin-right: 8rpx;
}

.search-bar {
  padding: 20rpx 32rpx;
  background: #fff;
}

.search-input-wrapper {
  display: flex;
  align-items: center;
  background: #f5f5f5;
  border-radius: 40rpx;
  padding: 0 28rpx;
  height: 80rpx;
}

.search-icon {
  font-size: 32rpx;
  margin-right: 16rpx;
}

.search-input {
  flex: 1;
  font-size: 28rpx;
}

.filter-tabs {
  display: flex;
  background: #fff;
  padding: 16rpx 32rpx;
  gap: 20rpx;
  border-top: 1rpx solid #f0f0f0;
}

.filter-tab {
  padding: 12rpx 32rpx;
  border-radius: 40rpx;
  font-size: 26rpx;
  color: #666;

  &.active {
    background: #667eea;
    color: #fff;
  }
}

.course-list {
  height: calc(100vh - 420rpx);
  padding: 24rpx 32rpx;
  padding-bottom: 180rpx;     // ✅ 底部舒适间距，与 TabBar 保持距离
  box-sizing: border-box;
  overflow-y: auto;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 120rpx 0;
}

.empty-icon {
  font-size: 120rpx;
  margin-bottom: 32rpx;
}

.empty-text {
  font-size: 28rpx;
  color: #999;
  margin-bottom: 32rpx;
}

.empty-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  border-radius: 40rpx;
  padding: 20rpx 48rpx;
  color: #fff;
  font-size: 28rpx;
}

.course-card {
  background: #fff;
  border-radius: 20rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
}

.course-cover {
  position: relative;
  width: 100%;
  height: 320rpx;
  border-radius: 16rpx;
  overflow: hidden;
  margin-bottom: 20rpx;
}

.cover-image {
  width: 100%;
  height: 100%;
}

.cover-placeholder {
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.placeholder-icon {
  font-size: 80rpx;
}

.course-status {
  position: absolute;
  top: 16rpx;
  right: 16rpx;
  padding: 8rpx 20rpx;
  border-radius: 20rpx;
  font-size: 22rpx;

  &.active {
    background: rgba(72, 187, 120, 0.9);
    color: #fff;
  }

  &.inactive {
    background: rgba(255, 153, 153, 0.9);
    color: #fff;
  }
}

.course-info {
  margin-bottom: 16rpx;
}

.course-name {
  font-size: 32rpx;
  font-weight: bold;
  display: block;
  margin-bottom: 12rpx;
}

.course-meta {
  display: flex;
  flex-wrap: wrap;
  margin-bottom: 12rpx;
}

.meta-item {
  font-size: 24rpx;
  color: #999;
  margin-right: 24rpx;
}

.course-price {
  display: flex;
  align-items: baseline;
}

.price-label {
  font-size: 24rpx;
  color: #ff4d4f;
}

.price-value {
  font-size: 40rpx;
  font-weight: bold;
  color: #ff4d4f;
}

.course-actions {
  display: flex;
  border-top: 1rpx solid #f0f0f0;
  padding-top: 16rpx;
}

.action-btn {
  flex: 1;
  text-align: center;
  padding: 16rpx;
  border-radius: 12rpx;
  font-size: 26rpx;

  &.edit {
    background: #f5f5f5;
    color: #667eea;
    margin-right: 16rpx;
  }

  &.delete {
    background: #fff0f0;
    color: #ff4d4f;
  }
}

.tab-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  background: #fff;
  padding: 16rpx 0 32rpx;
  border-top: 1rpx solid #f0f0f0;
}

.tab-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;

  &.active {
    .tab-icon, .tab-text {
      color: #667eea;
    }
  }
}

.tab-icon {
  font-size: 40rpx;
  margin-bottom: 8rpx;
  color: #999;
}

.tab-text {
  font-size: 22rpx;
  color: #999;
}
</style>