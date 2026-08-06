<template>
  <view class="page">
    <view class="search-bar">
      <view class="search-input-wrap">
        <text class="search-icon">🔍</text>
        <input 
          class="search-input" 
          placeholder="搜索课程" 
          :value="keyword"
          @input="handleKeywordChange"
          @confirm="handleSearch"
        />
      </view>
    </view>

    <view class="filter-bar">
      <scroll-view scroll-x class="filter-scroll">
        <view class="filter-list">
          <view 
            class="filter-item" 
            :class="{ active: category === '' }"
            @click="setCategory('')"
          >
            全部
          </view>
          <view 
            class="filter-item" 
            v-for="cat in categories" 
            :key="cat"
            :class="{ active: category === cat }"
            @click="setCategory(cat)"
          >
            {{ cat }}
          </view>
        </view>
      </scroll-view>
    </view>

    <view class="course-list">
      <view 
        class="course-card" 
        v-for="course in courses" 
        :key="course.id"
        @click="goToDetail(course.id)"
      >
        <image class="course-cover" :src="course.cover_url || '/static/default-course.png'" mode="aspectFill" />
        <view class="course-info">
          <text class="course-name">{{ course.name }}</text>
          <text class="course-desc">{{ course.description }}</text>
          <view class="course-meta">
            <text class="course-category">{{ course.category }}</text>
            <text class="course-level">{{ course.level }}</text>
          </view>
          <view class="course-footer">
            <view class="price-area">
              <text class="course-price">¥{{ course.price }}</text>
              <text class="course-unit">/节</text>
            </view>
            <view class="course-stats">
              <text class="stat-item">{{ course.duration_minutes }}分钟</text>
              <text class="stat-item">限{{ course.max_capacity }}人</text>
            </view>
          </view>
        </view>
      </view>
    </view>

    <view class="loading-more" v-if="loading">
      <text>加载中...</text>
    </view>

    <view class="no-more" v-else-if="!hasMore && courses.length > 0">
      <text>没有更多了</text>
    </view>

    <view class="empty-state" v-else-if="courses.length === 0 && !loading">
      <text class="empty-icon">📭</text>
      <text class="empty-text">暂无课程</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { courseApi } from '@/api'

const keyword = ref('')
const category = ref('')
const courses = ref<any[]>([])
const page = ref(1)
const pageSize = 10
const loading = ref(false)
const hasMore = ref(true)

const categories = ['拉丁舞', '街舞', '瑜伽', '爵士舞', '肚皮舞', '芭蕾']

onMounted(() => {
  loadCourses()
})

async function loadCourses(isRefresh = false) {
  if (loading.value) return
  
  loading.value = true
  
  try {
    const res = await courseApi.list({
      page: isRefresh ? 1 : page.value,
      page_size: pageSize,
      keyword: keyword.value,
      category: category.value
    })
    
    if (isRefresh) {
      courses.value = res.data.items || []
      page.value = 1
    } else {
      courses.value = [...courses.value, ...(res.data.items || [])]
    }
    
    hasMore.value = (res.data.items || []).length === pageSize
    if (!isRefresh) page.value++
  } catch (e) {
    console.error('加载课程失败', e)
  } finally {
    loading.value = false
  }
}

function handleKeywordChange(e: any) {
  keyword.value = e.detail.value
}

function handleSearch() {
  loadCourses(true)
}

function setCategory(cat: string) {
  category.value = cat
  loadCourses(true)
}

function goToDetail(id: number) {
  uni.navigateTo({ url: `/pages/course/detail?id=${id}` })
}
</script>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 120rpx;
}

.search-bar {
  padding: 20rpx 30rpx;
  background: #fff;
}

.search-input-wrap {
  display: flex;
  align-items: center;
  background: #f5f5f5;
  border-radius: 40rpx;
  padding: 20rpx 30rpx;
}

.search-icon {
  font-size: 32rpx;
  margin-right: 16rpx;
}

.search-input {
  flex: 1;
  font-size: 28rpx;
  background: transparent;
}

.filter-bar {
  background: #fff;
  padding: 20rpx 0;
  border-bottom: 2rpx solid #f0f0f0;
}

.filter-scroll {
  white-space: nowrap;
}

.filter-list {
  display: inline-flex;
  padding: 0 30rpx;
  gap: 20rpx;
}

.filter-item {
  padding: 16rpx 32rpx;
  border-radius: 30rpx;
  font-size: 26rpx;
  color: #666;
  background: #f5f5f5;
  
  &.active {
    background: #1989fa;
    color: #fff;
  }
}

.course-list {
  padding: 20rpx 30rpx;
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.course-card {
  display: flex;
  background: #fff;
  border-radius: 20rpx;
  overflow: hidden;
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.06);
}

.course-cover {
  width: 240rpx;
  height: 200rpx;
  flex-shrink: 0;
}

.course-info {
  flex: 1;
  padding: 20rpx;
  display: flex;
  flex-direction: column;
}

.course-name {
  font-size: 32rpx;
  font-weight: bold;
  color: #333;
}

.course-desc {
  font-size: 24rpx;
  color: #999;
  margin-top: 12rpx;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.course-meta {
  display: flex;
  gap: 16rpx;
  margin-top: 16rpx;
}

.course-category,
.course-level {
  font-size: 22rpx;
  color: #999;
  background: #f5f5f5;
  padding: 6rpx 16rpx;
  border-radius: 20rpx;
}

.course-footer {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-top: auto;
}

.price-area {
  display: flex;
  align-items: baseline;
}

.course-price {
  font-size: 36rpx;
  font-weight: bold;
  color: #ff6b6b;
}

.course-unit {
  font-size: 22rpx;
  color: #999;
  margin-left: 6rpx;
}

.course-stats {
  display: flex;
  gap: 20rpx;
}

.stat-item {
  font-size: 22rpx;
  color: #999;
}

.loading-more,
.no-more {
  text-align: center;
  padding: 30rpx;
  font-size: 26rpx;
  color: #999;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 100rpx 0;
}

.empty-icon {
  font-size: 80rpx;
  margin-bottom: 20rpx;
}

.empty-text {
  font-size: 28rpx;
  color: #999;
}
</style>