import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@dance-saas/api-client'
import router from '@/router'

interface AdminInfo {
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

export const useAuthStore = defineStore('admin-auth', () => {
  const token = ref<string>(localStorage.getItem('token') || '')
  const refreshToken = ref<string>(localStorage.getItem('refreshToken') || '')
  const tenantSlug = ref<string>(localStorage.getItem('tenantSlug') || '')
  const adminInfo = ref<AdminInfo | null>(null)

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
    adminInfo.value = null
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

    try {
      const payload = JSON.parse(atob(res.data.access_token.split('.')[1]))
      setTenantSlug(params.tenant_slug || 'dance-school')
    } catch {
      // ignore
    }

    await fetchAdminInfo()
    return res.data
  }

  async function fetchAdminInfo() {
    if (!token.value) return
    try {
      const res = await apiClient.get('/auth/me')
      adminInfo.value = {
        id: res.data.id || 1,
        phone: res.data.phone || '',
        nickname: res.data.nickname || '管理员',
        avatar: res.data.avatar,
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
    adminInfo,
    isLoggedIn,
    login,
    logout,
    fetchAdminInfo,
    setToken,
    setTenantSlug,
    clearToken,
  }
})