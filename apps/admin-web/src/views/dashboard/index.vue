<template>
  <div class="page-container">
    <div class="page-header">
      <h2>控制台</h2>
      <span style="color:#909399;font-size:14px">最后更新：刚刚</span>
    </div>

    <div class="stat-cards">
      <div class="stat-card">
        <div class="stat-card-header">
          <span class="stat-label">总用户数</span>
          <div class="stat-icon" style="background:linear-gradient(135deg,#667eea,#764ba2)"><el-icon><User /></el-icon></div>
        </div>
        <div class="stat-value">{{ totalUsers }}</div>
        <div class="stat-trend">↑ 12% 较上月</div>
      </div>

      <div class="stat-card">
        <div class="stat-card-header">
          <span class="stat-label">活跃课程</span>
          <div class="stat-icon" style="background:linear-gradient(135deg,#f093fb,#f5576c)"><el-icon><Reading /></el-icon></div>
        </div>
        <div class="stat-value">{{ activeCourses }}</div>
        <div class="stat-trend">↑ 3 门新课</div>
      </div>

      <div class="stat-card">
        <div class="stat-card-header">
          <span class="stat-label">本月排期</span>
          <div class="stat-icon" style="background:linear-gradient(135deg,#4facfe,#00f2fe)"><el-icon><Calendar /></el-icon></div>
        </div>
        <div class="stat-value">{{ monthlySchedules }}</div>
        <div class="stat-trend">↑ 8% 较上月</div>
      </div>

      <div class="stat-card">
        <div class="stat-card-header">
          <span class="stat-label">本月预约</span>
          <div class="stat-icon" style="background:linear-gradient(135deg,#43e97b,#38f9d7)"><el-icon><Checked /></el-icon></div>
        </div>
        <div class="stat-value">{{ monthlyBookings }}</div>
        <div class="stat-trend">↑ 23% 较上月</div>
      </div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px">
      <el-card shadow="never">
        <template #header><span style="font-weight:600">最近预约</span></template>
        <el-table :data="recentBookings" size="small" style="width:100%">
          <el-table-column prop="student" label="学员" />
          <el-table-column prop="course" label="课程" />
          <el-table-column prop="time" label="时间" width="160" />
          <el-table-column prop="status" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.status === '已签到' ? 'success' : 'warning'" size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header><span style="font-weight:600">禁用教师</span></template>
        <el-table :data="disabledTeachers" size="small" style="width:100%">
          <el-table-column prop="name" label="姓名" />
          <el-table-column prop="phone" label="手机号" />
          <el-table-column prop="speciality" label="专长" />
          <el-table-column label="操作" width="120">
            <template #default>
              <el-button type="primary" size="small" link>启用</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { User, Reading, Calendar, Checked } from '@element-plus/icons-vue'
import { apiClient } from '@dance-saas/api-client'

const totalUsers = ref(0)
const activeCourses = ref(0)
const monthlySchedules = ref(0)
const monthlyBookings = ref(0)
const recentBookings = ref<any[]>([])
const disabledTeachers = ref<any[]>([])

async function fetchDashboard() {
  try {
    const res = await apiClient.get('/admin/dashboard')
    const data = res.data
    totalUsers.value = data.total_users
    activeCourses.value = data.active_courses
    monthlySchedules.value = data.monthly_schedules
    monthlyBookings.value = data.monthly_bookings
    recentBookings.value = data.recent_bookings
    disabledTeachers.value = data.disabled_teachers
  } catch (_) {}
}

onMounted(() => {
  fetchDashboard()
})
</script>