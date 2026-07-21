import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/courses',
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/register/index.vue'),
    meta: { title: '注册' },
  },
  {
    path: '/courses',
    name: 'Courses',
    component: () => import('@/views/courses/index.vue'),
    meta: { title: '课程列表', requiresAuth: true },
  },
  {
    path: '/courses/:id',
    name: 'CourseDetail',
    component: () => import('@/views/course-detail/index.vue'),
    meta: { title: '课程详情', requiresAuth: true },
  },
  {
    path: '/courses/:id/schedule',
    name: 'CourseSchedule',
    component: () => import('@/views/schedule/index.vue'),
    meta: { title: '课程排期', requiresAuth: true },
  },
  {
    path: '/my-bookings',
    name: 'MyBookings',
    component: () => import('@/views/my-bookings/index.vue'),
    meta: { title: '我的预约', requiresAuth: true },
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('@/views/profile/index.vue'),
    meta: { title: '个人中心', requiresAuth: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to, _from, next) => {
  document.title = (to.meta.title as string) || '舞蹈约课'

  if (to.meta.requiresAuth) {
    const userStore = useUserStore()
    if (!userStore.token) {
      next({ name: 'Login', query: { redirect: to.fullPath } })
      return
    }
    
    // 如果用户已登录但用户信息为空，自动获取
    if (!userStore.userInfo) {
      try {
        await userStore.fetchUserInfo()
      } catch {
        // 获取失败，可能Token已过期，跳转到登录
        userStore.clearToken()
        next({ name: 'Login', query: { redirect: to.fullPath } })
        return
      }
    }
  }

  next()
})

export default router