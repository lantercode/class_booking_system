<template>
  <div class="my-bookings-container">
    <header class="page-header">
      <el-button text @click="$router.push('/courses')">
        <el-icon><ArrowLeft /></el-icon>
        返回课程
      </el-button>
      <span class="header-title">我的预约</span>
      <div style="width: 60px"></div>
    </header>

    <div class="tab-bar">
      <div
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-item"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
        <span v-if="tab.count() > 0" class="tab-count">{{ tab.count() }}</span>
      </div>
    </div>

    <div class="booking-list">
      <div v-if="filteredBookings.length === 0" class="empty-wrapper">
        <el-empty description="暂无预约记录" />
      </div>

      <div
        v-for="booking in filteredBookings"
        :key="booking.id"
        class="booking-card"
        @click="goToCourse(booking.courseId)"
      >
        <img :src="booking.cover" :alt="booking.courseName" class="booking-cover" />
        <div class="booking-info">
          <div class="booking-header">
            <span class="booking-name">{{ booking.courseName }}</span>
            <el-tag :type="getStatusTagType(booking.status)" size="small">
              {{ booking.statusLabel }}
            </el-tag>
          </div>
          <div class="booking-meta">
            <span><el-icon><Calendar /></el-icon> {{ booking.date }}</span>
            <span><el-icon><Clock /></el-icon> {{ booking.startTime }} - {{ booking.endTime }}</span>
          </div>
          <div class="booking-meta">
            <span><el-icon><User /></el-icon> {{ booking.teacherName }}</span>
            <span><el-icon><Location /></el-icon> {{ booking.classroom }}</span>
          </div>
          <div class="booking-footer">
            <span class="booking-time">预约时间：{{ booking.createdAt }}</span>
            <el-button
              v-if="booking.status === 'confirmed'"
              type="danger"
              text
              size="small"
              @click.stop="handleCancel(booking)"
            >
              取消预约
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <el-dialog
      v-model="cancelVisible"
      title="取消预约"
      width="320px"
      :close-on-click-modal="false"
    >
      <p>确定要取消「{{ cancelTarget?.courseName }}」的预约吗？</p>
      <p class="cancel-hint">取消后不可恢复，请谨慎操作。</p>
      <template #footer>
        <el-button @click="cancelVisible = false">再想想</el-button>
        <el-button type="danger" @click="confirmCancel">确定取消</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Calendar, Clock, User, Location } from '@element-plus/icons-vue'
import { bookingApi, scheduleApi, courseApi, type Booking } from '@dance-saas/api-client'

const router = useRouter()

interface BookingView {
  id: number
  courseId: number
  courseName: string
  cover: string
  date: string
  startTime: string
  endTime: string
  teacherName: string
  classroom: string
  status: string
  statusLabel: string
  createdAt: string
  scheduleId: number
}

const STATUS_MAP: Record<number, { key: string; label: string }> = {
  1: { key: 'confirmed', label: '已预约' },
  2: { key: 'cancelled', label: '已取消' },
  3: { key: 'completed', label: '已签到' },
  4: { key: 'completed', label: '已完成' },
}

const bookings = ref<BookingView[]>([])
const loading = ref(false)
const activeTab = ref<string>('all')
const cancelVisible = ref(false)
const cancelTarget = ref<BookingView | null>(null)

const tabs = computed(() => [
  { key: 'all', label: '全部', count: () => bookings.value.length },
  { key: 'confirmed', label: '已预约', count: () => bookings.value.filter((b) => b.status === 'confirmed').length },
  { key: 'completed', label: '已完成', count: () => bookings.value.filter((b) => b.status === 'completed').length },
  { key: 'cancelled', label: '已取消', count: () => bookings.value.filter((b) => b.status === 'cancelled').length },
])

const filteredBookings = computed(() => {
  if (activeTab.value === 'all') return bookings.value
  return bookings.value.filter((b) => b.status === activeTab.value)
})

function getStatusTagType(status: string) {
  const m: Record<string, string> = { confirmed: 'primary', completed: 'success', cancelled: 'info' }
  return m[status] || 'info'
}

async function fetchBookings() {
  loading.value = true
  try {
    const [bRes, sRes, cRes] = await Promise.all([
      bookingApi.list({ page_size: 200 }),
      scheduleApi.list({ page_size: 500 }),
      courseApi.list({ page_size: 200 }),
    ])

    const scheduleMap = new Map<number, any>()
    for (const s of sRes.data.items) scheduleMap.set(s.id, s)

    const courseMap = new Map<number, string>()
    for (const c of cRes.data.items) courseMap.set(c.id, c.name)

    bookings.value = bRes.data.items.map((b) => {
      const s = scheduleMap.get(b.schedule_id)
      const statusInfo = STATUS_MAP[b.status] || { key: 'unknown', label: '未知' }
      return {
        id: b.id,
        courseId: s?.course_id || 0,
        courseName: courseMap.get(s?.course_id || 0) || '未知课程',
        cover: s?.course_id ? `https://picsum.photos/seed/${s.course_id}/400/240` : '',
        date: s?.start_at?.slice(0, 10) || '',
        startTime: s ? new Date(s.start_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '',
        endTime: s ? new Date(s.end_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '',
        teacherName: s ? `教师#${s.teacher_id}` : '未知教师',
        classroom: s?.classroom_id ? `教室#${s.classroom_id}` : '未指定',
        status: statusInfo.key,
        statusLabel: statusInfo.label,
        createdAt: b.booked_at?.slice(0, 10) || '',
        scheduleId: b.schedule_id,
      }
    })
  } catch (_) {} finally {
    loading.value = false
  }
}

function goToCourse(courseId: number) {
  if (courseId) router.push(`/courses/${courseId}`)
}

function handleCancel(booking: BookingView) {
  cancelTarget.value = booking
  cancelVisible.value = true
}

async function confirmCancel() {
  if (!cancelTarget.value) return
  try {
    await bookingApi.cancel(cancelTarget.value.id, '用户取消')
    ElMessage.success('预约已取消')
    cancelVisible.value = false
    cancelTarget.value = null
    fetchBookings()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '取消失败')
  }
}

onMounted(() => {
  fetchBookings()
})
</script>

<style scoped lang="scss">
.my-bookings-container {
  min-height: 100vh;
  background: #f5f7fa;
  max-width: 800px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);

  .header-title {
    font-size: 16px;
    font-weight: 600;
    color: #303133;
  }
}

.tab-bar {
  display: flex;
  background: #fff;
  margin: 16px 16px 0;
  border-radius: 12px;
  padding: 4px;
  gap: 4px;

  .tab-item {
    flex: 1;
    text-align: center;
    padding: 8px 0;
    font-size: 14px;
    color: #606266;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
    position: relative;

    &.active {
      background: #409eff;
      color: #fff;
      font-weight: 500;
    }

    .tab-count {
      margin-left: 4px;
      font-size: 12px;
    }
  }
}

.booking-list {
  padding: 16px;
}

.empty-wrapper {
  padding: 60px 0;
}

.booking-card {
  display: flex;
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  cursor: pointer;
  transition: transform 0.2s;

  &:active {
    transform: scale(0.98);
  }

  .booking-cover {
    width: 100px;
    height: 100px;
    object-fit: cover;
    flex-shrink: 0;
  }

  .booking-info {
    flex: 1;
    padding: 12px;
    min-width: 0;
  }

  .booking-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;

    .booking-name {
      font-size: 15px;
      font-weight: 600;
      color: #303133;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .booking-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    font-size: 13px;
    color: #909399;
    margin-bottom: 4px;

    span {
      display: flex;
      align-items: center;
      gap: 4px;
    }
  }

  .booking-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 8px;

    .booking-time {
      font-size: 12px;
      color: #c0c4cc;
    }
  }
}

.cancel-hint {
  font-size: 13px;
  color: #909399;
  margin-top: 8px;
}
</style>