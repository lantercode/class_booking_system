import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@dance-saas/api-client'
import router from '@/router'

interface UserInfo {
  id: number
  phone: string
  nickname: string
  avatar?: string
}

interface LoginParams {
  phone: string
  password: string
  tenant_slug?: string
}

interface RegisterParams {
  phone: string
  password: string
  nickname: string
  tenant_slug: string
  verify_code: string
}

export const useUserStore = defineStore('user', () => {
  const token = ref<string>(localStorage.getItem('token') || '')
  const refreshToken = ref<string>(localStorage.getItem('refreshToken') || '')
  const tenantSlug = ref<string>(localStorage.getItem('tenantSlug') || '')
  const userInfo = ref<UserInfo | null>(null)

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
    userInfo.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')
    localStorage.removeItem('tenantSlug')
  }

  async function login(params: LoginParams) {
    const res = await apiClient.post('/auth/login', {
      phone: params.phone,
      password: params.password,
      tenant_slug: params.tenant_slug || 'default',
    })

    setToken(res.data.access_token, res.data.refresh_token)

    // 从 JWT 中解码 tenant_id 并存储
    try {
      const payload = JSON.parse(atob(res.data.access_token.split('.')[1]))
      setTenantSlug(params.tenant_slug || 'dance-school')
    } catch {
      // 解码失败不影响主流程
    }

    await fetchUserInfo()
    return res.data
  }

  async function register(params: RegisterParams) {
    const res = await apiClient.post('/auth/register', params)
    return res.data
  }

  async function fetchUserInfo() {
    if (!token.value) return
    try {
      const res = await apiClient.get('/auth/me')
      userInfo.value = res.data
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
    userInfo,
    isLoggedIn,
    login,
    register,
    logout,
    fetchUserInfo,
    setToken,
    clearToken,
  }
})