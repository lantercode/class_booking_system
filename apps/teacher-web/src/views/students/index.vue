<template>
  <div class="students-container">
    <header class="page-header">
      <el-button text @click="$router.back()">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
      <span class="header-title">学员列表</span>
      <div style="width: 60px"></div>
    </header>

    <div class="info-card">
      <div class="info-row">
        <el-icon><Collection /></el-icon>
        <span>课程：{{ scheduleInfo.courseName }}</span>
      </div>
      <div class="info-row">
        <el-icon><Clock /></el-icon>
        <span>时间：{{ scheduleInfo.time }}</span>
      </div>
      <div class="info-row">
        <el-icon><Location /></el-icon>
        <span>教室：{{ scheduleInfo.classroom }}</span>
      </div>
    </div>

    <div class="stats-bar">
      <div class="stat-item">
        <span class="stat-num">{{ students.length }}</span>
        <span class="stat-label">已预约</span>
      </div>
      <div class="stat-item">
        <span class="stat-num attended">{{ attendedCount }}</span>
        <span class="stat-label">已签到</span>
      </div>
      <div class="stat-item">
        <span class="stat-num absent">{{ absentCount }}</span>
        <span class="stat-label">未签到</span>
      </div>
    </div>

    <div class="students-list">
      <div v-for="student in students" :key="student.id" class="student-item">
        <div class="student-left">
          <el-avatar :size="44">
            <el-icon :size="22"><UserFilled /></el-icon>
          </el-avatar>
          <div class="student-info">
            <span class="student-name">{{ student.nickname }}</span>
            <span class="student-phone">{{ student.phone }}</span>
          </div>
        </div>
        <div class="student-right">
          <el-tag
            :type="student.status === 'attended' ? 'success' : student.status === 'cancelled' ? 'info' : 'warning'"
            size="small"
          >
            {{ student.status === 'attended' ? '已签到' : student.status === 'cancelled' ? '已取消' : '待签到' }}
          </el-tag>
          <el-button
            v-if="student.status === 'confirmed'"
            size="small"
            type="primary"
            text
            @click="checkIn(student)"
          >
            签到
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Collection, Clock, Location, UserFilled } from '@element-plus/icons-vue'
import { bookingApi, scheduleApi, userApi } from '@dance-saas/api-client'

const route = useRoute()
const scheduleId = Number(route.params.scheduleId) || 1

interface StudentBooking {
  id: number
  avatar: string
  nickname: string
  phone: string
  status: string
  userId: number
}

const scheduleInfo = ref({ courseName: '', time: '', classroom: '' })
const students = ref<StudentBooking[]>([])
const loading = ref(false)

const attendedCount = computed(() => students.value.filter((s) => s.status === 'attended').length)
const absentCount = computed(() => students.value.filter((s) => s.status === 'confirmed').length)

async function fetchData() {
  loading.value = true
  try {
    const [bRes, sRes] = await Promise.all([
      bookingApi.list({ schedule_id: scheduleId, page_size: 500 }),
      scheduleApi.getById(scheduleId),
    ])

    const schedule = sRes.data
    scheduleInfo.value = {
      courseName: `课程#${schedule.course_id}`,
      time: `${schedule.start_at.slice(0, 16)} - ${schedule.end_at.slice(11, 16)}`,
      classroom: schedule.classroom_id ? `教室#${schedule.classroom_id}` : '未指定',
    }

    const bookings = bRes.data.items
    const userIds = [...new Set(bookings.map((b) => b.student_id))]
    const userMap = new Map<number, string>()
    const phoneMap = new Map<number, string>()

    if (userIds.length > 0) {
      try {
        const uRes = await userApi.list({ page_size: 500 })
        for (const u of uRes.data.items) {
          userMap.set(u.id, u.nickname || u.phone)
          phoneMap.set(u.id, u.phone)
        }
      } catch (_) {}
    }

    students.value = bookings.map((b) => ({
      id: b.id,
      avatar: '',
      nickname: userMap.get(b.student_id) || `学员#${b.student_id}`,
      phone: phoneMap.get(b.student_id) || '',
      status: b.status === 2 ? 'attended' : b.status === 4 ? 'cancelled' : 'confirmed',
      userId: b.student_id,
    }))
  } catch (_) {} finally {
    loading.value = false
  }
}

async function checkIn(student: StudentBooking) {
  try {
    await bookingApi.checkIn(student.id)
    student.status = 'attended'
    ElMessage.success(`${student.nickname} 签到成功`)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '签到失败')
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped lang="scss">
.students-container {
  min-height: 100vh;
  background: linear-gradient(180deg, #fef5f9 0%, #f0f2ff 30%, #f5f7fa 100%);
  max-width: 800px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.04);
  position: sticky;
  top: 0;
  z-index: 50;

  .header-title {
    font-size: 17px;
    font-weight: 700;
    color: #1a1a2e;
  }
}

.info-card {
  background: linear-gradient(135deg, #667eea, #764ba2);
  margin: 16px;
  border-radius: 16px;
  padding: 20px;
  color: #fff;
  box-shadow: 0 4px 16px rgba(102, 126, 234, 0.25);

  .info-row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    margin-bottom: 8px;

    &:last-child {
      margin-bottom: 0;
    }
  }
}

.stats-bar {
  display: flex;
  justify-content: space-around;
  background: #fff;
  margin: 0 16px 12px;
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);

  .stat-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;

    .stat-num {
      font-size: 24px;
      font-weight: 700;
      color: #667eea;

      &.attended { color: #67c23a; }
      &.absent { color: #e6a23c; }
    }

    .stat-label {
      font-size: 12px;
      color: #909399;
    }
  }
}

.students-list {
  background: #fff;
  margin: 0 16px 16px;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);

  .student-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 16px;
    border-bottom: 1px solid #f5f5f5;

    &:last-child {
      border-bottom: none;
    }

    .student-left {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .student-info {
      display: flex;
      flex-direction: column;
      gap: 2px;

      .student-name {
        font-size: 15px;
        font-weight: 600;
        color: #1a1a2e;
      }

      .student-phone {
        font-size: 12px;
        color: #c0c4cc;
      }
    }

    .student-right {
      display: flex;
      align-items: center;
      gap: 12px;
    }
  }
}
</style>