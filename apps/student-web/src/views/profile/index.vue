<template>
  <div class="profile-container">
    <header class="page-header">
      <el-button text @click="$router.push('/courses')">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
      <span class="header-title">个人中心</span>
      <div style="width: 60px"></div>
    </header>

    <div class="profile-card">
      <div class="avatar-wrapper">
        <div class="avatar-ring">
          <el-avatar :size="80" :src="userStore.userInfo?.avatar">
            <el-icon :size="40"><UserFilled /></el-icon>
          </el-avatar>
          <span class="avatar-dot"></span>
        </div>
        <div class="user-info">
          <span class="nickname">{{ userStore.userInfo?.nickname || '学员' }}</span>
          <span class="phone">{{ userStore.userInfo?.phone || '' }}</span>
        </div>
        <el-icon class="edit-icon" :size="18"><Edit /></el-icon>
      </div>

      <div class="stats-row">
        <div class="stat-item">
          <div class="stat-icon pending">
            <el-icon :size="18"><Clock /></el-icon>
          </div>
          <span class="stat-value">{{ pendingCount }}</span>
          <span class="stat-label">待上课</span>
        </div>
        <div class="stat-divider"></div>
        <div class="stat-item">
          <div class="stat-icon done">
            <el-icon :size="18"><CircleCheckFilled /></el-icon>
          </div>
          <span class="stat-value">{{ completedCount }}</span>
          <span class="stat-label">已完成</span>
        </div>
        <div class="stat-divider"></div>
        <div class="stat-item">
          <div class="stat-icon total">
            <el-icon :size="18"><Tickets /></el-icon>
          </div>
          <span class="stat-value">{{ totalCount }}</span>
          <span class="stat-label">总预约</span>
        </div>
      </div>
    </div>

    <div class="section-title">
      <span class="title-dot"></span>
      常用功能
    </div>
    <div class="menu-section">
      <div class="menu-item" @click="goToMyBookings">
        <div class="menu-left">
          <div class="menu-icon" style="background: #ecf5ff">
            <el-icon :size="20" color="#409eff"><Calendar /></el-icon>
          </div>
          <div class="menu-text">
            <span class="menu-name">我的预约</span>
            <span class="menu-desc">查看和管理预约记录</span>
          </div>
        </div>
        <div class="menu-right">
          <el-badge :value="pendingCount" :hidden="pendingCount === 0" />
          <el-icon><ArrowRight /></el-icon>
        </div>
      </div>

      <div class="menu-item">
        <div class="menu-left">
          <div class="menu-icon" style="background: #f0f9eb">
            <el-icon :size="20" color="#67c23a"><Star /></el-icon>
          </div>
          <div class="menu-text">
            <span class="menu-name">我的会员卡</span>
            <span class="menu-desc">查看会员权益和余额</span>
          </div>
        </div>
        <div class="menu-right">
          <span class="menu-hint">暂无</span>
          <el-icon><ArrowRight /></el-icon>
        </div>
      </div>

      <div class="menu-item">
        <div class="menu-left">
          <div class="menu-icon" style="background: #fdf6ec">
            <el-icon :size="20" color="#e6a23c"><Collection /></el-icon>
          </div>
          <div class="menu-text">
            <span class="menu-name">上课记录</span>
            <span class="menu-desc">查看历史上课记录</span>
          </div>
        </div>
        <div class="menu-right">
          <span class="menu-hint">{{ completedCount }}节</span>
          <el-icon><ArrowRight /></el-icon>
        </div>
      </div>
    </div>

    <div class="section-title">
      <span class="title-dot"></span>
      设置
    </div>
    <div class="menu-section">
      <div class="menu-item">
        <div class="menu-left">
          <div class="menu-icon" style="background: #f5f7fa">
            <el-icon :size="20" color="#303133"><User /></el-icon>
          </div>
          <div class="menu-text">
            <span class="menu-name">编辑资料</span>
            <span class="menu-desc">修改昵称和头像</span>
          </div>
        </div>
        <el-icon><ArrowRight /></el-icon>
      </div>

      <div class="menu-item">
        <div class="menu-left">
          <div class="menu-icon" style="background: #f5f7fa">
            <el-icon :size="20" color="#303133"><Lock /></el-icon>
          </div>
          <div class="menu-text">
            <span class="menu-name">修改密码</span>
            <span class="menu-desc">定期更换密码更安全</span>
          </div>
        </div>
        <el-icon><ArrowRight /></el-icon>
      </div>

      <div class="menu-item">
        <div class="menu-left">
          <div class="menu-icon" style="background: #f5f7fa">
            <el-icon :size="20" color="#909399"><InfoFilled /></el-icon>
          </div>
          <div class="menu-text">
            <span class="menu-name">关于</span>
            <span class="menu-desc">版本和帮助信息</span>
          </div>
        </div>
        <div class="menu-right">
          <span class="menu-hint">v1.0.0</span>
          <el-icon><ArrowRight /></el-icon>
        </div>
      </div>
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
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  ArrowRight,
  UserFilled,
  Calendar,
  Star,
  InfoFilled,
  Edit,
  Clock,
  CircleCheckFilled,
  Tickets,
  Collection,
  User,
  Lock,
  SwitchButton,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { bookingApi } from '@dance-saas/api-client'

const router = useRouter()
const userStore = useUserStore()

const pendingCount = ref(0)
const completedCount = ref(0)
const totalCount = ref(0)

async function fetchStats() {
  try {
    const res = await bookingApi.list({ page_size: 500 })
    const bookings = res.data.items
    totalCount.value = bookings.length
    pendingCount.value = bookings.filter(
      (b) => b.status === 1
    ).length
    completedCount.value = bookings.filter(
      (b) => b.status === 3
    ).length
  } catch (_) {}
}

onMounted(() => {
  fetchStats()
})

function goToMyBookings() {
  router.push('/my-bookings')
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

  &::after {
    content: '';
    position: absolute;
    bottom: -20px;
    left: -20px;
    width: 80px;
    height: 80px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.04);
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
        letter-spacing: -0.5px;
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

      &:hover {
        opacity: 1;
      }
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
        display: flex;
        align-items: center;
        justify-content: center;

        &.pending {
          background: rgba(255, 255, 255, 0.15);
        }

        &.done {
          background: rgba(255, 255, 255, 0.15);
        }

        &.total {
          background: rgba(255, 255, 255, 0.15);
        }
      }

      .stat-value {
        font-size: 24px;
        font-weight: 800;
        letter-spacing: -1px;
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
  text-transform: uppercase;
  letter-spacing: 1px;

  .title-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #667eea;
  }
}

.menu-section {
  background: #fff;
  margin: 0 16px 12px;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);

  .menu-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 18px;
    border-bottom: 1px solid #f5f5f5;
    cursor: pointer;
    transition: background 0.2s;

    &:last-child {
      border-bottom: none;
    }

    &:active {
      background: #fafafa;
    }

    .menu-left {
      display: flex;
      align-items: center;
      gap: 14px;
      flex: 1;
      min-width: 0;

      .menu-icon {
        width: 40px;
        height: 40px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }

      .menu-text {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;

        .menu-name {
          font-size: 15px;
          font-weight: 600;
          color: #1a1a2e;
        }

        .menu-desc {
          font-size: 12px;
          color: #c0c4cc;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }
    }

    .menu-right {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-shrink: 0;

      .menu-hint {
        font-size: 13px;
        color: #c0c4cc;
      }
    }
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