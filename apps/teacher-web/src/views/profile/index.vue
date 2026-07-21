<template>
  <div class="profile-container">
    <header class="page-header">
      <el-button text @click="$router.push('/courses')">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
      <span class="header-title">教师档案</span>
      <div style="width: 60px"></div>
    </header>

    <div class="profile-card">
      <div class="avatar-wrapper">
        <div class="avatar-ring">
          <el-avatar :size="80" :src="authStore.teacherInfo?.avatar">
            <el-icon :size="40"><UserFilled /></el-icon>
          </el-avatar>
          <span class="avatar-dot"></span>
        </div>
        <div class="user-info">
          <span class="nickname">{{ authStore.teacherInfo?.nickname || '教师' }}</span>
          <span class="phone">{{ authStore.teacherInfo?.phone || '' }}</span>
        </div>
      </div>

      <div class="stats-row">
        <div class="stat-item">
          <div class="stat-icon">
            <el-icon :size="18"><Collection /></el-icon>
          </div>
          <span class="stat-value">{{ totalCourses }}</span>
          <span class="stat-label">课程数</span>
        </div>
        <div class="stat-divider"></div>
        <div class="stat-item">
          <div class="stat-icon">
            <el-icon :size="18"><Calendar /></el-icon>
          </div>
          <span class="stat-value">{{ totalSchedules }}</span>
          <span class="stat-label">排期数</span>
        </div>
      </div>
    </div>

    <div class="section-title">
      <span class="title-dot"></span>
      资料编辑
    </div>
    <div class="form-card">
      <el-form label-position="top" size="large">
        <el-form-item label="姓名">
          <el-input v-model="profileForm.nickname" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="个人简介">
          <el-input
            v-model="profileForm.intro"
            type="textarea"
            :rows="3"
            placeholder="介绍一下你自己"
            maxlength="120"
            show-word-limit
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" class="save-btn" @click="handleSave">
            保存修改
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="logout-section">
      <el-button class="logout-btn" @click="handleLogout">
        <el-icon><SwitchButton /></el-icon>
        退出登录
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { ArrowLeft, UserFilled, Edit, Collection, Calendar, SwitchButton } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { courseApi, scheduleApi, teacherApi } from '@dance-saas/api-client'

const authStore = useAuthStore()

const profileForm = reactive({
  nickname: '',
  intro: '',
})

const totalCourses = ref(0)
const totalSchedules = ref(0)

async function fetchTeacherInfo() {
  try {
    const res = await teacherApi.getInfo()
    profileForm.nickname = res.data.nickname || ''
    profileForm.intro = res.data.intro || ''
    // 更新store中的教师信息
    authStore.teacherInfo = {
      ...authStore.teacherInfo,
      nickname: res.data.nickname,
      intro: res.data.intro,
    }
  } catch (_) {}
}

async function fetchStats() {
  try {
    const [cRes, sRes] = await Promise.all([
      courseApi.list({ page_size: 500 }),
      scheduleApi.list({ page_size: 500 }),
    ])
    totalCourses.value = cRes.data.items.length
    totalSchedules.value = sRes.data.items.length
  } catch (_) {}
}

onMounted(() => {
  fetchTeacherInfo()
  fetchStats()
})

async function handleSave() {
  try {
    const res = await teacherApi.updateInfo({
      nickname: profileForm.nickname,
      intro: profileForm.intro,
    })
    // 更新store中的教师信息
    authStore.teacherInfo = {
      ...authStore.teacherInfo,
      nickname: res.data.nickname,
      intro: res.data.intro,
    }
    ElMessage.success('保存成功')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '保存失败')
  }
}

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '退出确认', {
      confirmButtonText: '确定退出',
      cancelButtonText: '取消',
      type: 'warning',
    })
    authStore.logout()
  } catch {
    // 取消
  }
}
</script>

<style scoped lang="scss">
.profile-container {
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

.profile-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  margin: 20px 16px;
  border-radius: 24px;
  padding: 28px 24px 20px;
  color: #fff;
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    top: -40px;
    right: -30px;
    width: 140px;
    height: 140px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.06);
  }

  .avatar-wrapper {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 24px;
    position: relative;
    z-index: 1;

    .avatar-ring {
      position: relative;
      padding: 3px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.2);

      .avatar-dot {
        position: absolute;
        bottom: 2px;
        right: 2px;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background: #67c23a;
        border: 3px solid #667eea;
      }
    }

    .user-info {
      display: flex;
      flex-direction: column;
      gap: 4px;
      flex: 1;

      .nickname {
        font-size: 22px;
        font-weight: 700;
      }

      .phone {
        font-size: 14px;
        opacity: 0.75;
      }
    }

    .edit-icon {
      opacity: 0.6;
      cursor: pointer;
      transition: opacity 0.2s;
      &:hover { opacity: 1; }
    }
  }

  .stats-row {
    display: flex;
    align-items: center;
    justify-content: space-around;
    padding: 20px 0 4px;
    border-top: 1px solid rgba(255, 255, 255, 0.15);
    position: relative;
    z-index: 1;

    .stat-item {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 6px;

      .stat-icon {
        width: 36px;
        height: 36px;
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.15);
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .stat-value {
        font-size: 24px;
        font-weight: 800;
      }

      .stat-label {
        font-size: 12px;
        opacity: 0.7;
      }
    }

    .stat-divider {
      width: 1px;
      height: 40px;
      background: rgba(255, 255, 255, 0.15);
    }
  }
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 20px;
  font-size: 13px;
  font-weight: 600;
  color: #909399;
  letter-spacing: 1px;

  .title-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #667eea;
  }
}

.form-card {
  background: #fff;
  margin: 0 16px 12px;
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);

  .save-btn {
    width: 100%;
    border-radius: 14px;
    height: 48px;
    font-size: 16px;
    font-weight: 600;
    background: linear-gradient(135deg, #667eea, #764ba2);
    border: none;
  }
}

.logout-section {
  padding: 20px 16px 40px;
  text-align: center;

  .logout-btn {
    width: 100%;
    max-width: 300px;
    border-radius: 14px;
    padding: 14px 0;
    font-size: 15px;
    font-weight: 600;
    color: #f56c6c;
    border: 1.5px solid #fde2e2;
    background: #fef0f0;
    transition: all 0.2s;

    &:hover {
      background: #fde2e2;
      color: #e63946;
      border-color: #fbc4c4;
    }
  }
}
</style>