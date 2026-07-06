<template>
  <div class="courses-container">
    <header class="courses-header">
      <div class="header-left">
        <h1>课程列表</h1>
      </div>
      <div class="header-right">
        <el-dropdown trigger="click">
          <span class="user-info">
            <el-avatar :size="32" :icon="UserFilled" />
            <span class="nickname">{{ userStore.userInfo?.nickname || '学员' }}</span>
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="handleLogout">
                <el-icon><SwitchButton /></el-icon>
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <main class="courses-main">
      <div v-if="loading" class="loading-wrapper">
        <el-skeleton :rows="3" animated />
      </div>

      <div v-else-if="courses.length === 0" class="empty-wrapper">
        <el-empty description="暂无课程">
          <el-button type="primary" @click="fetchCourses">刷新</el-button>
        </el-empty>
      </div>

      <div v-else class="courses-grid">
        <el-card
          v-for="course in courses"
          :key="course.id"
          class="course-card"
          shadow="hover"
        >
          <template #header>
            <div class="course-card-header">
              <span class="course-name">{{ course.name }}</span>
              <el-tag :type="course.status === 1 ? 'success' : 'info'" size="small">
                {{ course.status === 1 ? '可约' : '已关闭' }}
              </el-tag>
            </div>
          </template>
          <div class="course-info">
            <p><el-icon><Clock /></el-icon> {{ course.duration || 60 }} 分钟</p>
            <p><el-icon><User /></el-icon> 教师：{{ course.teacher_name || '待定' }}</p>
            <p><el-icon><Location /></el-icon> {{ course.classroom || '待定' }}</p>
            <p v-if="course.capacity">
              <el-icon><Tickets /></el-icon>
              剩余名额：{{ course.remaining || course.capacity }} / {{ course.capacity }}
            </p>
          </div>
          <div class="course-actions">
            <el-button type="primary" :disabled="course.status !== 1" @click="handleBooking(course)">
              立即预约
            </el-button>
          </div>
        </el-card>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  UserFilled,
  ArrowDown,
  SwitchButton,
  Clock,
  User,
  Location,
  Tickets,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { apiClient } from '@dance-saas/api-client'

const userStore = useUserStore()

interface Course {
  id: number
  name: string
  status: number
  duration?: number
  teacher_name?: string
  classroom?: string
  capacity?: number
  remaining?: number
}

const courses = ref<Course[]>([])
const loading = ref(false)

async function fetchCourses() {
  loading.value = true
  try {
    const res = await apiClient.get('/courses')
    courses.value = res.data?.items || res.data || []
  } catch (err: any) {
    const msg = err.response?.data?.detail || '获取课程列表失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

function handleBooking(course: Course) {
  ElMessage.info(`预约课程：${course.name}（功能开发中）`)
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
  background: #f5f7fa;
}

.courses-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);

  .header-left h1 {
    font-size: 20px;
    color: #303133;
    margin: 0;
  }

  .header-right .user-info {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    font-size: 14px;
    color: #606266;

    .nickname {
      max-width: 120px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
}

.courses-main {
  padding: 24px;
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
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}

.course-card {
  .course-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .course-name {
      font-size: 16px;
      font-weight: 600;
      color: #303133;
    }
  }

  .course-info {
    p {
      display: flex;
      align-items: center;
      gap: 6px;
      margin: 8px 0;
      font-size: 14px;
      color: #606266;
    }
  }

  .course-actions {
    margin-top: 16px;
    text-align: right;
  }
}
</style>