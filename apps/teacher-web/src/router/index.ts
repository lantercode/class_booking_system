import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/courses',
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '教师登录' },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/register/index.vue'),
    meta: { title: '教师注册' },
  },
  {
    path: '/courses',
    name: 'Courses',
    component: () => import('@/views/courses/index.vue'),
    meta: { title: '我的课程', requiresAuth: true },
  },
  {
    path: '/courses/create',
    name: 'CourseCreate',
    component: () => import('@/views/courses/create.vue'),
    meta: { title: '创建课程', requiresAuth: true },
  },
  {
    path: '/courses/:id/edit',
    name: 'CourseEdit',
    component: () => import('@/views/courses/create.vue'),
    meta: { title: '编辑课程', requiresAuth: true },
  },
  {
    path: '/schedule',
    name: 'Schedule',
    component: () => import('@/views/schedule/index.vue'),
    meta: { title: '排期管理', requiresAuth: true },
  },
  {
    path: '/students/:scheduleId',
    name: 'Students',
    component: () => import('@/views/students/index.vue'),
    meta: { title: '学员列表', requiresAuth: true },
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('@/views/profile/index.vue'),
    meta: { title: '教师档案', requiresAuth: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to, _from, next) => {
  document.title = (to.meta.title as string) || '舞蹈约课 - 教师端'

  if (to.meta.requiresAuth) {
    const authStore = useAuthStore()
    if (!authStore.token) {
      next({ name: 'Login', query: { redirect: to.fullPath } })
      return
    }
    
    // 如果用户已登录但用户信息为空，自动获取
    if (!authStore.teacherInfo) {
      try {
        await authStore.fetchTeacherInfo()
      } catch {
        // 获取失败，可能Token已过期，跳转到登录
        authStore.clearToken()
        next({ name: 'Login', query: { redirect: to.fullPath } })
        return
      }
    }
  }

  next()
})

export default router