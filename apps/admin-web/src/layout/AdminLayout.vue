<template>
  <el-container class="admin-layout">
    <el-aside :width="isCollapse ? '64px' : '220px'" class="admin-sidebar">
      <div class="sidebar-header">
        <div class="logo-icon" :class="{ collapsed: isCollapse }">
          <el-icon :size="24">
            <Management />
          </el-icon>
        </div>
        <transition name="fade">
          <span v-show="!isCollapse" class="logo-text">约课管理</span>
        </transition>
      </div>

      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        :collapse-transition="false"
        background-color="#1a1a2e"
        text-color="#a0a0b8"
        active-text-color="#fff"
        router
        class="sidebar-menu"
      >
        <template v-for="item in menuItems" :key="item.path">
          <el-sub-menu v-if="item.children" :index="item.path">
            <template #title>
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.title }}</span>
            </template>
            <el-menu-item v-for="child in item.children" :key="child.path" :index="child.path">
              <el-icon><component :is="child.icon" /></el-icon>
              <span>{{ child.title }}</span>
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="item.path">
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="admin-header">
        <div class="header-left">
          <el-icon class="collapse-btn" :size="20" @click="isCollapse = !isCollapse">
            <Fold v-if="!isCollapse" />
            <Expand v-else />
          </el-icon>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/dashboard' }"> 首页 </el-breadcrumb-item>
            <el-breadcrumb-item v-if="currentTitle">
              {{ currentTitle }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-dropdown trigger="click">
            <div class="user-info">
              <el-avatar :size="32" :src="authAvatarPreview" icon="UserFilled" />
              <span class="user-name">{{ authStore.adminInfo?.nickname || '管理员' }}</span>
              <el-icon><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="openProfileDialog">
                  <el-icon><User /></el-icon>
                  个人资料
                </el-dropdown-item>
                <el-dropdown-item disabled>
                  <el-icon><Lock /></el-icon>
                  修改密码（FUTURE）
                </el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <div class="admin-content-wrapper">
        <el-main class="admin-main">
          <router-view />
        </el-main>
        <footer class="admin-footer">
          <div class="footer-content">
            <a
              href="https://beian.mps.gov.cn/#/query/webSearch?code=51012202002638"
              rel="noreferrer"
              target="_blank"
              class="footer-link"
            >
              <img
                src="https://beian.mps.gov.cn/img/logo01.dd7ff50e.png"
                alt="公安备案"
                class="footer-icon"
              />
              <span>川公网安备51012202002638号</span>
            </a>
            <a
              href="https://beian.miit.gov.cn/"
              target="_blank"
              rel="noopener noreferrer"
              class="footer-link"
            >
              <span>蜀ICP备2026050989号-1</span>
            </a>
          </div>
        </footer>
      </div>
    </el-container>

    <!-- 个人资料弹窗 -->
    <el-dialog
      v-model="profileDialogVisible"
      title="个人资料"
      width="480px"
      :close-on-click-modal="false"
      top="12vh"
    >
      <el-form ref="profileFormRef" :model="{ nickname: profileNickname }" :rules="profileRules" label-width="80px">
        <el-form-item label="头像">
          <div class="profile-avatar-row">
            <el-avatar :size="64" :src="profileAvatarPreview" icon="UserFilled" />
            <el-upload
              class="profile-avatar-uploader"
              v-bind="avatarUploadProps"
            >
              <el-button type="primary" :loading="profileUploading" size="small">
                上传头像
              </el-button>
            </el-upload>
            <span class="profile-avatar-tip">支持 JPG / PNG / WEBP，最大 5MB</span>
          </div>
        </el-form-item>
        <el-form-item label="昵称" prop="nickname">
          <el-input v-model="profileNickname" maxlength="20" placeholder="请输入昵称" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input :model-value="authStore.adminInfo?.phone || ''" disabled />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="profileDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="profileLoading" @click="handleProfileSave">
          保存
        </el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup lang="ts">
import { authApi, commonApi } from '@dance-saas/api-client'
import type { UploadProps } from 'element-plus'
import {
  ArrowDown,
  Avatar,
  Calendar,
  Collection,
  CreditCard,
  Expand,
  Fold,
  Key,
  Lock,
  Management,
  OfficeBuilding,
  Reading,
  Setting,
  SwitchButton,
  User,
  UserFilled,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { resolveAvatarUrl, useAuthStore } from '@/stores/auth'

interface MenuItem {
  path: string
  title: string
  icon: any
  children?: MenuItem[]
}

const route = useRoute()
const authStore = useAuthStore()
const isCollapse = ref(false)

// --- 个人资料弹窗 ---
const profileDialogVisible = ref(false)
const profileLoading = ref(false)
const profileUploading = ref(false)
const profileNickname = ref('')
const profileAvatarKey = ref<string | null>(null)
const profileAvatarPreview = computed(() => resolveAvatarUrl(profileAvatarKey.value))
const authAvatarPreview = computed(() => resolveAvatarUrl(authStore.adminInfo?.avatar))

const profileRules: FormRules = {
  nickname: [
    { required: true, message: '请输入昵称', trigger: 'blur' },
    { min: 2, max: 20, message: '昵称长度 2-20 个字符', trigger: 'blur' },
  ],
}
const profileFormRef = ref<FormInstance>()

function openProfileDialog() {
  profileNickname.value = authStore.adminInfo?.nickname || ''
  profileAvatarKey.value = authStore.adminInfo?.avatar || null
  profileDialogVisible.value = true
}

/** 头像上传：使用自定义 http-request，走 api-client 拦截器注入的 token + tenant-slug */
async function handleAvatarUpload(file: File) {
  profileUploading.value = true
  try {
    const res = await commonApi.uploadImage(file, 'avatar')
    profileAvatarKey.value = res.data.object_key
    ElMessage.success('头像上传成功')
  } catch (e: any) {
    ElMessage.error(e?.msg || '头像上传失败')
  } finally {
    profileUploading.value = false
  }
  return false // 阻止 el-upload 默认行为
}

const avatarUploadProps: Partial<UploadProps> = {
  showFileList: false,
  accept: 'image/jpeg,image/png,image/webp',
  limit: 1,
  beforeUpload: (file) => {
    const maxSize = 5 * 1024 * 1024
    if (file.size > maxSize) {
      ElMessage.error('图片大小不能超过 5MB')
      return false
    }
    return true
  },
  httpRequest: async (opts) => {
    if (opts.file) await handleAvatarUpload(opts.file as File)
  },
}

async function handleProfileSave() {
  const valid = await profileFormRef.value?.validate().catch(() => false)
  if (!valid) return

  profileLoading.value = true
  try {
    const payload: { nickname?: string; avatar_url?: string } = {}
    const currentNickname = authStore.adminInfo?.nickname || ''
    const currentAvatar = authStore.adminInfo?.avatar || null

    if (profileNickname.value !== currentNickname) {
      payload.nickname = profileNickname.value
    }
    if (profileAvatarKey.value !== currentAvatar) {
      payload.avatar_url = profileAvatarKey.value || undefined
    }
    if (Object.keys(payload).length === 0) {
      ElMessage.info('没有需要保存的变更')
      profileDialogVisible.value = false
      return
    }

    const res = await authApi.patchMe(payload)
    // 同步更新 Pinia store
    const updated = res.data
    authStore.setAdminInfo({
      id: authStore.adminInfo?.id ?? updated.id,
      phone: authStore.adminInfo?.phone ?? updated.phone,
      nickname: updated.nickname,
      avatar: updated.avatar ?? undefined,
      roles: updated.roles || authStore.adminInfo?.roles,
    })
    ElMessage.success('个人资料更新成功')
    profileDialogVisible.value = false
  } catch (e: any) {
    ElMessage.error(e?.msg || '保存失败')
  } finally {
    profileLoading.value = false
  }
}

// --- 菜单 ---
const menuItems: MenuItem[] = [
  // { path: '/dashboard', title: '控制台', icon: Odometer },
  { path: '/users', title: '用户管理', icon: User },
  { path: '/roles', title: '角色权限', icon: Key },
  { path: '/teachers', title: '教师管理', icon: Avatar },
  { path: '/students', title: '学员管理', icon: UserFilled },
  { path: '/courses', title: '课程管理', icon: Reading },
  { path: '/classrooms', title: '教室管理', icon: OfficeBuilding },
  { path: '/schedules', title: '排期管理', icon: Calendar },
  { path: '/bookings', title: '预约管理', icon: Calendar },
  { path: '/card-types', title: '卡产品管理', icon: Collection },
  { path: '/membership', title: '会员卡管理', icon: CreditCard },
  { path: '/tenant', title: '机构设置', icon: Setting },
]

const activeMenu = computed(() => route.path)
const currentTitle = computed(() => {
  const item = menuItems.find(m => m.path === route.path)
  return item?.title || ''
})

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '退出确认', {
      confirmButtonText: '确定退出',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await authStore.logout()
  } catch {
    // 取消退出
  }
}
</script>

<style scoped lang="scss">
.admin-layout {
  height: 100vh;
}

.admin-sidebar {
  background: #1a1a2e;
  overflow: hidden;
  transition: width 0.3s;

  .sidebar-header {
    height: 60px;
    display: flex;
    align-items: center;
    padding: 0 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);

    .logo-icon {
      width: 36px;
      height: 36px;
      border-radius: 10px;
      background: linear-gradient(135deg, #667eea, #764ba2);
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      flex-shrink: 0;
      transition: margin 0.3s;
    }

    .logo-text {
      margin-left: 12px;
      font-size: 16px;
      font-weight: 700;
      color: #fff;
      white-space: nowrap;
    }
  }

  .sidebar-menu {
    border-right: none;

    :deep(.el-menu-item),
    :deep(.el-sub-menu__title) {
      &:hover {
        background: rgba(102, 126, 234, 0.15) !important;
      }
    }

    :deep(.el-menu-item.is-active) {
      background: linear-gradient(90deg, rgba(102, 126, 234, 0.3), transparent) !important;
      border-right: 3px solid #667eea;
    }
  }
}

.admin-header {
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  z-index: 10;

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .collapse-btn {
    cursor: pointer;
    color: #909399;
    &:hover {
      color: #667eea;
    }
  }

  .header-right {
    .user-info {
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      padding: 4px 8px;
      border-radius: 8px;
      transition: background 0.2s;

      &:hover {
        background: #f5f7fa;
      }

      .user-name {
        font-size: 14px;
        color: #303133;
      }
    }
  }
}

.admin-content-wrapper {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px);
}

.admin-main {
  flex: 1;
  background: #f0f2f5;
  padding: 24px;
  overflow-y: auto;
  min-height: 0;
}

.admin-footer {
  flex-shrink: 0;
  height: 48px;
  background: #fff;
  border-top: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: center;

  .footer-content {
    display: flex;
    align-items: center;
    gap: 24px;
  }

  .footer-link {
    display: flex;
    align-items: center;
    gap: 6px;
    color: #909399;
    font-size: 13px;
    text-decoration: none;
    transition: color 0.2s;

    &:hover {
      color: #667eea;
    }

    .footer-icon {
      width: 16px;
      height: 16px;
    }
  }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.profile-avatar-row {
  display: flex;
  align-items: center;
  gap: 16px;

  .profile-avatar-tip {
    font-size: 12px;
    color: #909399;
  }
}
</style>
