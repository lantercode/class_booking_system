import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@dance-saas/api-client'
import router from '@/router'
import { getTenantSlug } from '@/config/tenant'

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
    // 机构标识由部署配置注入，登录页不再要求用户输入
    const slug = params.tenant_slug?.trim() || getTenantSlug()
    const res = await apiClient.post('/auth/login', {
      phone: params.phone,
      password: params.password,
      tenant_slug: slug,
    })

    setToken(res.data.access_token, res.data.refresh_token)
    setTenantSlug(slug)

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