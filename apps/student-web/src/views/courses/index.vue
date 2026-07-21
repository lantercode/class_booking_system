<template>
  <div class="courses-container">
    <header class="courses-header">
      <div class="header-left">
        <h1>精选课程</h1>
        <span class="header-sub">发现适合你的舞蹈课程</span>
      </div>
      <div class="header-right">
        <el-button text @click="$router.push('/my-bookings')">
          <el-icon><Tickets /></el-icon>
          我的预约
        </el-button>
        <el-dropdown trigger="click">
          <span class="user-info">
            <el-avatar :size="32" :icon="UserFilled" />
            <span class="nickname">{{ userStore.userInfo?.nickname || '学员' }}</span>
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="$router.push('/profile')">
                <el-icon><User /></el-icon>
                个人中心
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
        <h2>找到属于你的舞蹈节奏</h2>
        <p>从古典到现代，从业余到专业，开启你的舞蹈之旅</p>
      </div>
      <div class="hero-decoration">
        <span class="deco-circle c1"></span>
        <span class="deco-circle c2"></span>
        <span class="deco-circle c3"></span>
      </div>
    </div>

    <div class="filter-bar">
      <div class="filter-tabs">
        <span
          v-for="tab in filterTabs"
          :key="tab.key"
          class="filter-tab"
          :class="{ active: activeFilter === tab.key }"
          @click="activeFilter = tab.key"
        >
          {{ tab.label }}
        </span>
      </div>
    </div>

    <main class="courses-main">
      <div v-if="loading" class="loading-wrapper">
        <el-skeleton :rows="3" animated />
      </div>

      <div v-else-if="filteredCourses.length === 0" class="empty-wrapper">
        <el-empty description="暂无课程">
          <el-button type="primary" @click="fetchCourses">刷新</el-button>
        </el-empty>
      </div>

      <div v-else class="courses-grid">
        <div
          v-for="course in filteredCourses"
          :key="course.id"
          class="course-card"
          :class="{ 'is-disabled': course.status !== 1 }"
          @click="goToCourse(course.id)"
        >
          <div class="card-cover">
            <img :src="course.cover" :alt="course.name" />
            <div class="cover-overlay">
              <div class="difficulty-badge" :class="'difficulty-' + course.difficulty">
                {{ getDifficultyLabel(course.difficulty) }}
              </div>
              <div class="status-dot" :class="course.status === 1 ? 'online' : 'offline'"></div>
            </div>
          </div>
          <div class="card-body">
            <div class="card-tags">
              <span v-if="course.category" class="tag-chip">{{ course.category }}</span>
              <span v-if="course.level" class="tag-chip">{{ course.level }}</span>
            </div>
            <h3 class="card-title">{{ course.name }}</h3>
            <p class="card-desc">{{ course.description?.slice(0, 40) || '暂无简介' }}</p>
            <div class="card-meta">
              <div class="meta-item">
                <el-icon><Clock /></el-icon>
                <span>{{ course.duration }}分钟</span>
              </div>
            </div>
            <div class="card-footer">
              <div class="price-section">
                <span class="price-symbol">¥</span>
                <span class="price-value">{{ course.price }}</span>
                <span class="price-unit">/节</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import {
  UserFilled,
  ArrowDown,
  SwitchButton,
  Clock,
  Tickets,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { courseApi, type Course } from '@dance-saas/api-client'

const userStore = useUserStore()
const router = useRouter()

interface CourseView {
  id: number
  name: string
  cover: string
  description: string
  category: string
  level: string
  difficulty: string
  duration: number
  price: number
  capacity: number
  status: number
}

const COVER_PLACEHOLDER = 'https://picsum.photos/seed/dance/400/240'
const LEVEL_MAP: Record<string, string> = {
  '入门': 'beginner',
  '初级': 'beginner',
  '中级': 'intermediate',
  '高级': 'advanced',
}

function mapCourse(c: Course): CourseView {
  return {
    id: c.id,
    name: c.name,
    cover: c.cover_url || COVER_PLACEHOLDER,
    description: c.description || '',
    category: c.category || '',
    level: c.level || '',
    difficulty: LEVEL_MAP[c.level || ''] || 'beginner',
    duration: c.duration_minutes,
    price: c.price,
    capacity: c.max_capacity,
    status: c.status,
  }
}

function getDifficultyLabel(d: string): string {
  const m: Record<string, string> = { beginner: '入门', intermediate: '中级', advanced: '高级' }
  return m[d] || d
}

const courses = ref<CourseView[]>([])
const loading = ref(false)
const activeFilter = ref('all')

const filterTabs = [
  { key: 'all', label: '全部' },
  { key: 'beginner', label: '入门' },
  { key: 'intermediate', label: '中级' },
  { key: 'advanced', label: '高级' },
]

const filteredCourses = computed(() => {
  if (activeFilter.value === 'all') return courses.value
  return courses.value.filter((c) => c.difficulty === activeFilter.value)
})

async function fetchCourses() {
  loading.value = true
  try {
    const res = await courseApi.list({ page_size: 50 })
    courses.value = (res.data.items || []).map(mapCourse)
  } catch {
    courses.value = []
  } finally {
    loading.value = false
  }
}

function goToCourse(id: number) {
  router.push(`/courses/${id}`)
}

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '退出确认', {
      confirmButtonText: '确定退出',
      cancelButtonText: '取消',
      type: 'warning',
    })
    userStore.logout()
  } catch {
    // 用户取消，不执行任何操作
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

.courses-header {
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
    h1 {
      font-size: 20px;
      font-weight: 700;
      color: #1a1a2e;
      margin: 0;
      letter-spacing: -0.5px;
    }

    .header-sub {
      font-size: 12px;
      color: #909399;
      margin-left: 4px;
    }
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 12px;

    .user-info {
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      font-size: 14px;
      color: #606266;
      padding: 4px 8px;
      border-radius: 20px;
      transition: background 0.2s;

      &:hover {
        background: #f5f7fa;
      }

      .nickname {
        max-width: 80px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }
  }
}

.hero-banner {
  position: relative;
  margin: 20px 24px;
  padding: 40px 32px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
  border-radius: 24px;
  overflow: hidden;
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.25);

  .hero-content {
    position: relative;
    z-index: 2;

    h2 {
      font-size: 28px;
      font-weight: 800;
      color: #fff;
      margin: 0 0 12px;
      letter-spacing: -1px;
    }

    p {
      font-size: 15px;
      color: rgba(255, 255, 255, 0.85);
      margin: 0;
      line-height: 1.6;
    }
  }

  .hero-decoration {
    .deco-circle {
      position: absolute;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.1);

      &.c1 {
        width: 180px;
        height: 180px;
        top: -60px;
        right: -40px;
      }

      &.c2 {
        width: 100px;
        height: 100px;
        bottom: -30px;
        right: 100px;
      }

      &.c3 {
        width: 60px;
        height: 60px;
        top: 30px;
        right: 160px;
        background: rgba(255, 255, 255, 0.06);
      }
    }
  }
}

.filter-bar {
  padding: 0 24px;
  margin-bottom: 8px;

  .filter-tabs {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    padding-bottom: 4px;

    &::-webkit-scrollbar {
      display: none;
    }

    .filter-tab {
      flex-shrink: 0;
      padding: 8px 20px;
      border-radius: 20px;
      font-size: 14px;
      font-weight: 500;
      color: #606266;
      background: #fff;
      cursor: pointer;
      transition: all 0.25s;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);

      &.active {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: #fff;
        box-shadow: 0 4px 16px rgba(102, 126, 234, 0.35);
      }

      &:hover:not(.active) {
        color: #667eea;
        background: #f0f2ff;
      }
    }
  }
}

.courses-main {
  padding: 12px 24px 40px;
  max-width: 1200px;
  margin: 0 auto;
}

.loading-wrapper {
  padding: 40px 0;
}

.empty-wrapper {
  padding: 80px 0;
}

.courses-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.course-card {
  background: #fff;
  border-radius: 20px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.35s cubic-bezier(0.25, 0.8, 0.25, 1.2);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);

  &:hover {
    transform: translateY(-6px);
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.12);

    .card-cover img {
      transform: scale(1.08);
    }

    .cover-overlay {
      background: linear-gradient(
        to top,
        rgba(0, 0, 0, 0.5) 0%,
        transparent 60%
      );
    }
  }

  &.is-disabled {
    opacity: 0.7;

    .card-cover::after {
      content: '已关闭';
      position: absolute;
      top: 12px;
      right: 12px;
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 600;
      color: #fff;
      background: rgba(0, 0, 0, 0.5);
      backdrop-filter: blur(4px);
      z-index: 3;
    }
  }

  .card-cover {
    position: relative;
    height: 180px;
    overflow: hidden;

    img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      transition: transform 0.5s cubic-bezier(0.25, 0.8, 0.25, 1.2);
    }

    .cover-overlay {
      position: absolute;
      inset: 0;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      padding: 12px;
      background: linear-gradient(
        to top,
        rgba(0, 0, 0, 0.35) 0%,
        transparent 50%
      );
      transition: background 0.35s;
      z-index: 2;
    }

    .difficulty-badge {
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 600;
      color: #fff;
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);

      &.difficulty-beginner {
        background: rgba(103, 194, 58, 0.75);
      }

      &.difficulty-intermediate {
        background: rgba(230, 162, 60, 0.75);
      }

      &.difficulty-advanced {
        background: rgba(245, 108, 108, 0.75);
      }
    }

    .status-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.3);

      &.online {
        background: #67c23a;
        animation: pulse-dot 2s infinite;
      }

      &.offline {
        background: #909399;
      }
    }
  }

  .card-body {
    padding: 16px 18px 20px;
  }

  .card-tags {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-bottom: 10px;

    .tag-chip {
      padding: 2px 10px;
      border-radius: 10px;
      font-size: 11px;
      font-weight: 500;
      color: #667eea;
      background: #f0f2ff;
    }
  }

  .card-title {
    font-size: 18px;
    font-weight: 700;
    color: #1a1a2e;
    margin: 0 0 8px;
    line-height: 1.3;
    letter-spacing: -0.3px;
  }

  .card-desc {
    font-size: 13px;
    color: #909399;
    margin: 0 0 12px;
    line-height: 1.5;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .card-meta {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 14px;

    .meta-item {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      color: #909399;

      .el-icon {
        font-size: 14px;
        color: #c0c4cc;
      }
    }
  }

  .card-footer {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    padding-top: 14px;
    border-top: 1px solid #f5f5f5;

    .price-section {
      .price-symbol {
        font-size: 14px;
        font-weight: 700;
        color: #f56c6c;
        vertical-align: top;
      }

      .price-value {
        font-size: 26px;
        font-weight: 800;
        color: #f56c6c;
        letter-spacing: -1px;
        line-height: 1;
      }

      .price-unit {
        font-size: 12px;
        color: #909399;
        margin-left: 2px;
      }
    }

    .capacity-info {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 12px;
      color: #c0c4cc;
      padding: 4px 10px;
      border-radius: 10px;
      background: #f5f7fa;
    }
  }
}

@keyframes pulse-dot {
  0%,
  100% {
    box-shadow: 0 0 0 3px rgba(103, 194, 58, 0.3);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(103, 194, 58, 0.1);
  }
}

@media (max-width: 640px) {
  .hero-banner {
    margin: 12px 16px;
    padding: 28px 20px;
    border-radius: 16px;

    .hero-content h2 {
      font-size: 22px;
    }
  }

  .courses-main {
    padding: 12px 16px 40px;
  }

  .courses-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }
}
</style>