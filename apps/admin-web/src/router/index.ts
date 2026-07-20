import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/login/index.vue'),
      meta: { title: '管理员登录' },
    },
    {
      path: '/register',
      name: 'Register',
      component: () => import('@/views/register/index.vue'),
      meta: { title: '管理员注册' },
    },
    {
      path: '/',
      component: () => import('@/layout/AdminLayout.vue'),
      redirect: '/dashboard',
      children: [
        {
          path: 'dashboard',
          name: 'Dashboard',
          component: () => import('@/views/dashboard/index.vue'),
          meta: { title: '控制台', icon: 'Odometer' },
        },
        {
          path: 'users',
          name: 'Users',
          component: () => import('@/views/users/index.vue'),
          meta: { title: '用户管理', icon: 'User' },
        },
        {
          path: 'roles',
          name: 'Roles',
          component: () => import('@/views/roles/index.vue'),
          meta: { title: '角色权限', icon: 'Key' },
        },
        {
          path: 'teachers',
          name: 'Teachers',
          component: () => import('@/views/teachers/index.vue'),
          meta: { title: '教师管理', icon: 'Avatar' },
        },
        {
          path: 'students',
          name: 'Students',
          component: () => import('@/views/students/index.vue'),
          meta: { title: '学员管理', icon: 'UserFilled' },
        },
        {
          path: 'courses',
          name: 'AdminCourses',
          component: () => import('@/views/courses/index.vue'),
          meta: { title: '课程管理', icon: 'Reading' },
        },
        {
          path: 'schedules',
          name: 'AdminSchedules',
          component: () => import('@/views/schedules/index.vue'),
          meta: { title: '排期管理', icon: 'Calendar' },
        },
        {
          path: 'classrooms',
          name: 'Classrooms',
          component: () => import('@/views/classrooms/index.vue'),
          meta: { title: '教室管理', icon: 'OfficeBuilding' },
        },
        {
          path: 'tenant',
          name: 'Tenant',
          component: () => import('@/views/tenant/index.vue'),
          meta: { title: '机构设置', icon: 'Setting' },
        },
      ],
    },
  ],
})

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('token')
  if (to.path !== '/login' && to.path !== '/register' && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router