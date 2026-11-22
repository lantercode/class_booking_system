import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@dance-saas/api-client'
import router from '@/router'
import { getTenantSlug } from '@/config/tenant'

interface TeacherInfo {
  id: number
  phone: string
  nickname: string
  avatar?: string
  intro?: string
}

interface LoginParams {
  phone: string
  password: string
  tenant_slug?: string
}

export const useAuthStore = defineStore('teacher-auth', () => {
  const token = ref<string>(localStorage.getItem('token') || '')
  const refreshToken = ref<string>(localStorage.getItem('refreshToken') || '')
  const tenantSlug = ref<string>(localStorage.getItem('tenantSlug') || '')
  const teacherInfo = ref<TeacherInfo | null>(null)

  const isLoggedIn = computed(() => !!token.value)

  function setToken(access: string, refresh: string) {
    token.value = access
    refreshToken.value = refresh
    localStorage.setItem('token', access)
    localStorage.setItem('refreshToken', refresh)
  }

  function setTenantSlug(slug: string) {
    tenantSlug.value = slug
    localStorage.setItem('tenantSlug', slug)
  }

  function clearToken() {
    token.value = ''
    refreshToken.value = ''
    tenantSlug.value = ''
    teacherInfo.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')
    localStorage.removeItem('tenantSlug')
  }

  async function login(params: LoginParams) {
    // 机构标识由部署配置注入，登录页不再要求用户输入
    const slug = params.tenant_slug?.trim() || getTenantSlug()
    const res = await apiClient.post('/auth/login', {
      phone: params.phone,
      password: params.password,
      tenant_slug: slug,
    })
    setToken(res.data.access_token, res.data.refresh_token)
    setTenantSlug(slug)

    await fetchTeacherInfo()
    return res.data
  }

  async function fetchTeacherInfo() {
    if (!token.value) return
    try {
      const res = await apiClient.get('/auth/me')
      teacherInfo.value = {
        id: res.data.id || 1,
        phone: res.data.phone || '',
        nickname: res.data.nickname || '教师',
        avatar: res.data.avatar,
        intro: res.data.intro || '',
      }
    } catch {
      clearToken()
    }
  }

  async function logout() {
    try {
      await apiClient.post('/auth/logout')
    } catch {
      // ignore
    }
    clearToken()
    router.push('/login')
  }

  return {
    token,
    refreshToken,
    tenantSlug,
    teacherInfo,
    isLoggedIn,
    login,
    logout,
    fetchTeacherInfo,
    setToken,
    setTenantSlug,
    clearToken,
  }
})