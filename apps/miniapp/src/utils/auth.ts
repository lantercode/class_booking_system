import { authApi } from '@/api'

export function checkLogin(role?: string): boolean {
  const token = uni.getStorageSync('token')
  const userRole = uni.getStorageSync('user_role')
  
  if (!token) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    setTimeout(() => {
      redirectToHome()
    }, 1500)
    return false
  }
  
  if (role && userRole !== role) {
    uni.showToast({ title: '权限不足', icon: 'none' })
    setTimeout(() => {
      redirectToHome()
    }, 1500)
    return false
  }
  
  return true
}

export function getUserRole(): string | null {
  const token = uni.getStorageSync('token')
  const tenantSlug = uni.getStorageSync('tenant_slug')
  if (!token || !tenantSlug) {
    return null
  }
  return uni.getStorageSync('user_role') || null
}

export function isLoggedIn(): boolean {
  const token = uni.getStorageSync('token')
  const tenantSlug = uni.getStorageSync('tenant_slug')
  return !!(token && tenantSlug)
}

let isLoggingOut = false

export function logout() {
  if (isLoggingOut) return
  isLoggingOut = true
  
  uni.removeStorageSync('token')
  uni.removeStorageSync('refresh_token')
  uni.removeStorageSync('user_info')
  uni.removeStorageSync('user_role')
  uni.removeStorageSync('tenant_slug')
  
  setTimeout(() => {
    isLoggingOut = false
    uni.reLaunch({ url: '/pages/index/index' })
  }, 100)
}

export function clearAuth() {
  uni.removeStorageSync('token')
  uni.removeStorageSync('refresh_token')
  uni.removeStorageSync('user_info')
  uni.removeStorageSync('user_role')
  uni.removeStorageSync('tenant_slug')
}

export function getUserId(): number | null {
  const userInfo = uni.getStorageSync('user_info')
  if (userInfo) {
    try {
      return JSON.parse(userInfo).id
    } catch {
      return null
    }
  }
  return null
}

/**
 * 根据用户角色跳转到对应的主页
 * @param role 用户角色（可选，如果不传则从缓存读取）
 */
export function redirectToHome(role?: string) {
  const targetRole = role || uni.getStorageSync('user_role')
  
  console.log('🚀 跳转到主页，角色:', targetRole)
  
  if (!targetRole) {
    // 没有角色信息，回到授权页
    uni.reLaunch({ url: '/pages/index/index' })
    return
  }
  
  switch (targetRole) {
    case 'student':
      uni.reLaunch({ url: '/pages/student/courses/index' })
      break
      
    case 'teacher':
      // 教师端主页（根据实际情况调整路径）
      uni.reLaunch({ url: '/pages/teacher/dashboard/index' })
      break
      
    default:
      console.warn('⚠️ 未知角色:', targetRole, '，跳转到授权页')
      uni.reLaunch({ url: '/pages/index/index' })
  }
}

/**
 * 验证 Token 是否有效
 * 通过调用 /auth/me 接口验证
 */
export async function validateToken(): Promise<boolean> {
  try {
    const result = await authApi.getMe()
    const isValid = !!(result.code === 0 || result.code === 200)
    
    if (isValid) {
      console.log('✅ Token 有效')
    } else {
      console.log('❌ Token 无效或已过期')
      clearAuth()
    }
    
    return isValid
    
  } catch (error) {
    console.error('❌ 验证 Token 失败:', error)
    clearAuth()
    return false
  }
}