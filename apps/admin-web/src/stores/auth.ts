import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@dance-saas/api-client'
import router from '@/router'

interface AdminInfo {
  id: number
  phone: string
  nickname: string
  avatar?: string
  roles?: string[]
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
  const adminInfo = ref<AdminInfo | null>(
    localStorage.getItem('adminInfo') ? JSON.parse(localStorage.getItem('adminInfo')!) : null
  )

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

  function setAdminInfo(info: AdminInfo) {
    adminInfo.value = info
    localStorage.setItem('adminInfo', JSON.stringify(info))
    console.log('💾 用户信息已保存:', info)
  }

  function clearToken() {
    token.value = ''
    refreshToken.value = ''
    tenantSlug.value = ''
    adminInfo.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')
    localStorage.removeItem('tenantSlug')
    localStorage.removeItem('adminInfo')
  }

  async function login(params: LoginParams) {
    const slug = params.tenant_slug || 'dance-school'
    const res = await apiClient.post('/auth/login', {
      phone: params.phone,
      password: params.password,
      tenant_slug: slug,
    })
    setToken(res.data.access_token, res.data.refresh_token)
    setTenantSlug(slug)

    await fetchAdminInfo()
    return res.data
  }

  async function fetchAdminInfo() {
    if (!token.value) return
    try {
      const res = await apiClient.get('/auth/me')
      const info: AdminInfo = {
        id: res.data.id || 1,
        phone: res.data.phone || '',
        nickname: res.data.nickname || '管理员',
        avatar: res.data.avatar,
        roles: res.data.roles || [],
      }
      setAdminInfo(info)
      console.log('🔐 用户信息加载成功, roles:', info.roles)
    } catch (err: any) {
      console.error('❌ 获取用户信息失败:', err)
      if (err?.response?.status === 401) {
        clearToken()
      }
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

  function hasRole(role: string): boolean {
    return adminInfo.value?.roles?.includes(role) ?? false
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
    setAdminInfo,
    clearToken,
    hasRole,
  }
})