<template>
  <div class="courses-container">
    <header class="page-header">
      <div class="header-left">
        <h1>我的课程</h1>
        <span class="header-sub">共 {{ courses.length }} 门课程</span>
      </div>
      <div class="header-right">
        <el-button text @click="$router.push('/schedule')">
          <el-icon><Calendar /></el-icon>
          排期管理
        </el-button>
        <el-dropdown trigger="click">
          <span class="user-info">
            <el-avatar :size="32" :icon="UserFilled" />
            <span class="nickname">{{ authStore.teacherInfo?.nickname || '教师' }}</span>
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="$router.push('/profile')">
                <el-icon><User /></el-icon>
                教师档案
              </el-dropdown-item>
              <el-dropdown-item @click="handleLogout">
                <el-icon><SwitchButton /></el-icon>
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <div class="hero-banner">
      <div class="hero-content">
        <h2>教师工作台</h2>
        <p>管理课程、排期和学员，让教学更高效</p>
      </div>
      <div class="hero-deco">
        <span class="deco-circle c1"></span>
        <span class="deco-circle c2"></span>
      </div>
    </div>

    <div class="action-bar">
      <el-button type="primary" class="create-btn" @click="$router.push('/courses/create')">
        <el-icon><Plus /></el-icon>
        创建课程
      </el-button>
    </div>

    <main class="courses-main">
      <div v-if="loading" class="loading-wrapper">
        <el-skeleton :rows="3" animated />
      </div>
      <div v-else-if="courses.length === 0" class="empty-wrapper">
        <el-empty description="还没有课程">
          <el-button type="primary" @click="$router.push('/courses/create')">创建第一门课程</el-button>
        </el-empty>
      </div>
      <div v-else class="courses-grid">
        <div
          v-for="course in courses"
          :key="course.id"
          class="course-card"
          :class="{ 'is-offline': course.status !== 1 }"
        >
          <div class="card-cover">
            <img :src="course.cover" :alt="course.name" />
            <div class="cover-overlay">
              <span class="status-tag" :class="course.status === 1 ? 'online' : 'offline'">
                {{ course.status === 1 ? '开课中' : '已关闭' }}
              </span>
              <span class="diff-badge" :class="'diff-' + course.difficulty">
                {{ getDifficultyLabel(course.difficulty) }}
              </span>
            </div>
          </div>
          <div class="card-body">
            <div class="card-tags">
              <span v-for="tag in course.tags.slice(0, 3)" :key="tag" class="tag-chip">{{ tag }}</span>
            </div>
            <h3 class="card-title">{{ course.name }}</h3>
            <div class="card-stats">
              <div class="stat-item">
                <el-icon><UserFilled /></el-icon>
                <span>{{ course.studentCount }} 学员</span>
              </div>
              <div class="stat-item">
                <el-icon><Calendar /></el-icon>
                <span>{{ course.scheduleCount }} 排期</span>
              </div>
              <div class="stat-item">
                <span class="stat-price">¥{{ course.price }}</span>
                <span class="stat-unit">/节</span>
              </div>
            </div>
            <div class="card-actions">
              <el-button
                size="small"
                text
                type="primary"
                @click="$router.push(`/courses/${course.id}/edit`)"
              >
                <el-icon><Edit /></el-icon>
                编辑
              </el-button>
              <el-button
                size="small"
                text
                type="warning"
                @click="toggleStatus(course)"
              >
                <el-icon><VideoPause /></el-icon>
                {{ course.status === 1 ? '关闭' : '开启' }}
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import {
  UserFilled, ArrowDown, SwitchButton, User, Calendar, Plus, Edit, VideoPause,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { courseApi, type Course } from '@dance-saas/api-client'

interface CourseView {
  id: number
  name: string
  cover: string
  description: string
  difficulty: string
  duration: number
  price: number
  capacity: number
  status: number
  classroom: string
  tags: string[]
  studentCount: number
  scheduleCount: number
}

const COVER_PLACEHOLDER = 'https://picsum.photos/seed/tc/400/240'
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

const authStore = useAuthStore()
const courses = ref<CourseView[]>([])
const loading = ref(false)

async function fetchCourses() {
  loading.value = true
  try {
    const res = await courseApi.list({ page_size: 50 })
    courses.value = (res.data.items || []).map((c: Course) => ({
      id: c.id,
      name: c.name,
      cover: c.cover_url || COVER_PLACEHOLDER,
      description: c.description || '',
      difficulty: LEVEL_MAP[c.level || ''] || 'beginner',
      duration: c.duration_minutes,
      price: c.price,
      capacity: c.max_capacity,
      status: c.status,
      classroom: '舞蹈教室',
      tags: [c.category, c.level].filter(Boolean) as string[],
      studentCount: 0,
      scheduleCount: 0,
    }))
  } catch {
    courses.value = []
  } finally {
    loading.value = false
  }
}

async function toggleStatus(course: CourseView) {
  try {
    await ElMessageBox.confirm(
      `确定要${course.status === 1 ? '关闭' : '开启'}"${course.name}"吗？`,
      '操作确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' },
    )
    const newStatus = course.status === 1 ? 0 : 1
    await courseApi.update(course.id, { status: newStatus })
    course.status = newStatus
    ElMessage.success(newStatus === 1 ? '课程已开启' : '课程已关闭')
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.msg || '操作失败')
    }
  }
}

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '退出确认', {
      confirmButtonText: '确定退出', cancelButtonText: '取消', type: 'warning',
    })
    authStore.logout()
  } catch {
    // 取消
  }
}

onMounted(() => {
  fetchCourses()
})
</script>

<style scoped lang="scss">
.courses-container {
  min-height: 100vh;
  background: linear-gradient(180deg, #fef5f9 0%, #f0f2ff 30%, #f5f7fa 100%);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 24px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.04);
  position: sticky;
  top: 0;
  z-index: 50;

  .header-left {
    h1 { font-size: 20px; font-weight: 700; color: #1a1a2e; margin: 0; }
    .header-sub { font-size: 12px; color: #909399; margin-left: 4px; }
  }

  .header-right {
    display: flex; align-items: center; gap: 12px;
    .user-info {
      display: flex; align-items: center; gap: 8px; cursor: pointer;
      font-size: 14px; color: #606266; padding: 4px 8px; border-radius: 20px;
      transition: background 0.2s;
      &:hover { background: #f5f7fa; }
      .nickname { max-width: 80px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    }
  }
}

.hero-banner {
  position: relative;
  margin: 20px 24px;
  padding: 32px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 24px;
  overflow: hidden;
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.25);

  .hero-content {
    position: relative; z-index: 2;
    h2 { font-size: 26px; font-weight: 800; color: #fff; margin: 0 0 8px; }
    p { font-size: 14px; color: rgba(255,255,255,0.8); margin: 0; }
  }

  .hero-deco {
    .deco-circle {
      position: absolute; border-radius: 50%; background: rgba(255,255,255,0.08);
      &.c1 { width: 140px; height: 140px; top: -40px; right: -30px; }
      &.c2 { width: 80px; height: 80px; bottom: -20px; right: 80px; }
    }
  }
}

.action-bar {
  padding: 0 24px;
  margin-bottom: 16px;

  .create-btn {
    border-radius: 14px;
    padding: 12px 24px;
    font-size: 15px;
    font-weight: 600;
    background: linear-gradient(135deg, #667eea, #764ba2);
    border: none;
    box-shadow: 0 4px 16px rgba(102, 126, 234, 0.3);
    &:hover { opacity: 0.9; }
  }
}

.courses-main {
  padding: 0 24px 40px;
  max-width: 1200px;
  margin: 0 auto;
}

.loading-wrapper { padding: 40px 0; }
.empty-wrapper { padding: 80px 0; }

.courses-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.course-card {
  background: #fff;
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 4px 16px rgba(0,0,0,0.06);
  transition: all 0.35s cubic-bezier(0.25, 0.8, 0.25, 1.2);

  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 16px 32px rgba(0,0,0,0.1);
  }

  &.is-offline { opacity: 0.6; }

  .card-cover {
    position: relative;
    height: 160px;
    overflow: hidden;

    img {
      width: 100%; height: 100%; object-fit: cover;
      transition: transform 0.5s;
    }

    &:hover img { transform: scale(1.05); }

    .cover-overlay {
      position: absolute; inset: 0;
      display: flex; justify-content: space-between; align-items: flex-start;
      padding: 12px;
      background: linear-gradient(to top, rgba(0,0,0,0.4) 0%, transparent 50%);
      z-index: 2;
    }

    .status-tag {
      padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600; color: #fff;
      backdrop-filter: blur(8px);
      &.online { background: rgba(103, 194, 58, 0.75); }
      &.offline { background: rgba(144, 147, 153, 0.75); }
    }

    .diff-badge {
      padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600; color: #fff;
      backdrop-filter: blur(8px);
      &.diff-beginner { background: rgba(103, 194, 58, 0.75); }
      &.diff-intermediate { background: rgba(230, 162, 60, 0.75); }
      &.diff-advanced { background: rgba(245, 108, 108, 0.75); }
    }
  }

  .card-body {
    padding: 16px 18px;
  }

  .card-tags {
    display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px;
    .tag-chip {
      padding: 2px 10px; border-radius: 10px; font-size: 11px; font-weight: 500;
      color: #667eea; background: #f0f2ff;
    }
  }

  .card-title {
    font-size: 18px; font-weight: 700; color: #1a1a2e; margin: 0 0 14px;
  }

  .card-stats {
    display: flex; align-items: center; gap: 16px; margin-bottom: 14px;

    .stat-item {
      display: flex; align-items: center; gap: 4px; font-size: 13px; color: #909399;
      .stat-price { font-size: 18px; font-weight: 700; color: #f56c6c; }
      .stat-unit { font-size: 11px; color: #c0c4cc; }
    }
  }

  .card-actions {
    display: flex; gap: 8px; padding-top: 12px; border-top: 1px solid #f5f5f5;
  }
}
</style>