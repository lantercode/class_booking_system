<template>
  <div class="course-detail-container">
    <header class="detail-header">
      <el-button text @click="$router.back()">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
    </header>

    <main class="detail-main" v-if="course">
      <div class="cover-section">
        <img :src="course.cover" :alt="course.name" class="cover-image" />
        <div class="cover-overlay">
          <h1>{{ course.name }}</h1>
          <div class="cover-tags">
            <el-tag
              v-for="tag in course.tags"
              :key="tag"
              size="small"
              effect="plain"
              class="tag-item"
            >
              {{ tag }}
            </el-tag>
          </div>
        </div>
      </div>

      <div class="info-section">
        <div class="info-grid">
          <div class="info-item">
            <el-icon><Clock /></el-icon>
            <span>{{ course.duration }} 分钟</span>
          </div>
          <div class="info-item">
            <el-icon><DataLine /></el-icon>
            <el-tag :type="getDifficultyType(course.difficulty)" size="small">
              {{ getDifficultyLabel(course.difficulty) }}
            </el-tag>
          </div>
          <div class="info-item">
            <el-icon><Money /></el-icon>
            <span class="price">¥{{ course.price }}</span>
          </div>
          <div class="info-item">
            <el-icon><Location /></el-icon>
            <span>{{ course.classroom }}</span>
          </div>
          <div class="info-item">
            <el-icon><Tickets /></el-icon>
            <span>{{ course.capacity }} 人/班</span>
          </div>
        </div>
      </div>

      <div class="teacher-section">
        <h3>授课教师</h3>
        <div class="teacher-card">
          <el-avatar :size="56" :src="course.teacher.avatar" />
          <div class="teacher-info">
            <span class="teacher-name">{{ course.teacher.name }}</span>
            <span class="teacher-intro">{{ course.teacher.intro }}</span>
          </div>
        </div>
      </div>

      <div class="description-section">
        <h3>课程介绍</h3>
        <p class="description-text">{{ course.description }}</p>
      </div>

      <div class="action-bar">
        <el-button
          type="primary"
          size="large"
          :disabled="course.status !== 1"
          @click="goToSchedule"
        >
          {{ course.status === 1 ? '查看排期并预约' : '该课程暂不可约' }}
        </el-button>
      </div>
    </main>

    <div v-else-if="!loading" class="not-found">
      <el-empty description="课程不存在" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  Clock,
  DataLine,
  Money,
  Location,
  Tickets,
} from '@element-plus/icons-vue'
import { courseApi, type Course } from '@dance-saas/api-client'

const route = useRoute()
const router = useRouter()

interface CourseView {
  id: number
  name: string
  cover: string
  description: string
  teacher: { name: string; avatar: string; intro: string }
  difficulty: string
  duration: number
  price: number
  capacity: number
  status: number
  classroom: string
  tags: string[]
}

const COVER_PLACEHOLDER = 'https://picsum.photos/seed/dance/400/240'
const LEVEL_MAP: Record<string, string> = {
  '入门': 'beginner',
  '初级': 'beginner',
  '中级': 'intermediate',
  '高级': 'advanced',
}

function getDifficultyLabel(d: string): string {
  const m: Record<string, string> = { beginner: '入门', intermediate: '中级', advanced: '高级' }
  return m[d] || d
}

function getDifficultyType(d: string): 'success' | 'warning' | 'danger' {
  if (d === 'beginner') return 'success'
  if (d === 'intermediate') return 'warning'
  return 'danger'
}

const course = ref<CourseView | null>(null)
const loading = ref(false)

onMounted(async () => {
  const id = Number(route.params.id)
  if (!id) return
  loading.value = true
  try {
    const res = await courseApi.getById(id)
    const c: Course = res.data
    course.value = {
      id: c.id,
      name: c.name,
      cover: c.cover_url || COVER_PLACEHOLDER,
      description: c.description || '',
      teacher: { name: '授课教师', avatar: '', intro: '' },
      difficulty: LEVEL_MAP[c.level || ''] || 'beginner',
      duration: c.duration_minutes,
      price: c.price,
      capacity: c.max_capacity,
      status: c.status,
      classroom: '舞蹈教室',
      tags: [c.category, c.level].filter(Boolean) as string[],
    }
  } catch {
    course.value = null
  } finally {
    loading.value = false
  }
})

function goToSchedule() {
  if (course.value) {
    router.push(`/courses/${course.value.id}/schedule`)
  }
}
</script>

<style scoped lang="scss">
.course-detail-container {
  min-height: 100vh;
  background: #f5f7fa;
}

.detail-header {
  padding: 12px 24px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.detail-main {
  max-width: 800px;
  margin: 0 auto;
  padding-bottom: 80px;
}

.cover-section {
  position: relative;
  border-radius: 0 0 16px 16px;
  overflow: hidden;

  .cover-image {
    width: 100%;
    height: 240px;
    object-fit: cover;
  }

  .cover-overlay {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    padding: 24px;
    background: linear-gradient(transparent, rgba(0, 0, 0, 0.6));

    h1 {
      color: #fff;
      font-size: 24px;
      margin: 0 0 12px;
    }

    .cover-tags {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;

      .tag-item {
        --el-tag-bg-color: rgba(255, 255, 255, 0.2);
        --el-tag-border-color: rgba(255, 255, 255, 0.3);
        --el-tag-text-color: #fff;
      }
    }
  }
}

.info-section {
  background: #fff;
  margin: 16px;
  border-radius: 12px;
  padding: 20px;

  .info-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 16px;
  }

  .info-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    color: #606266;

    .price {
      color: #f56c6c;
      font-weight: 600;
      font-size: 16px;
    }
  }
}

.teacher-section {
  background: #fff;
  margin: 0 16px 16px;
  border-radius: 12px;
  padding: 20px;

  h3 {
    font-size: 16px;
    font-weight: 600;
    color: #303133;
    margin: 0 0 16px;
  }

  .teacher-card {
    display: flex;
    align-items: center;
    gap: 16px;

    .teacher-info {
      display: flex;
      flex-direction: column;
      gap: 6px;

      .teacher-name {
        font-size: 15px;
        font-weight: 600;
        color: #303133;
      }

      .teacher-intro {
        font-size: 13px;
        color: #909399;
        line-height: 1.5;
      }
    }
  }
}

.description-section {
  background: #fff;
  margin: 0 16px 16px;
  border-radius: 12px;
  padding: 20px;

  h3 {
    font-size: 16px;
    font-weight: 600;
    color: #303133;
    margin: 0 0 12px;
  }

  .description-text {
    font-size: 14px;
    color: #606266;
    line-height: 1.8;
    margin: 0;
  }
}

.action-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 12px 24px;
  background: #fff;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.06);
  display: flex;
  justify-content: center;
  z-index: 100;

  .el-button {
    width: 100%;
    max-width: 400px;
  }
}

.not-found {
  padding: 80px 0;
}
</style>