const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://106.14.206.226/api/v1'

console.log('API Base URL:', BASE_URL)

let isHandling401 = false
let hasLoggedOut = false

function buildQuery(params?: Record<string, any>): string {
  if (!params) return ''
  const parts = Object.entries(params)
    .filter(([_, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
  return parts.length > 0 ? '?' + parts.join('&') : ''
}

interface ApiResponse<T = any> {
  code: number
  data: T
  msg: string
}

/**
 * 创建带超时的 Promise 包装器
 * 防止 Promise 永远挂起导致 timeout 错误
 * 超时后会自动 abort 底层 uni.request，避免回调泄漏
 */
function withTimeout<T>(
  promise: Promise<T>, 
  ms: number, 
  errorMessage?: string,
  abortFn?: () => void
): Promise<T> {
  let timerId: ReturnType<typeof setTimeout>
  
  const timeoutPromise = new Promise<never>((_, reject) => {
    timerId = setTimeout(() => {
      abortFn?.()
      reject(new Error(errorMessage || `操作超时 (${ms}ms)`))
    }, ms)
  })
  
  return Promise.race([
    promise.then(
      (result) => {
        clearTimeout(timerId)
        return result
      },
      (err) => {
        clearTimeout(timerId)
        throw err
      }
    ),
    timeoutPromise
  ])
}

async function refreshToken(): Promise<boolean> {
  const storedRefreshToken = uni.getStorageSync('refresh_token')
  if (!storedRefreshToken) return false

  const tenantSlug = uni.getStorageSync('tenant_slug')
  const header: Record<string, string> = { 'Content-Type': 'application/json' }
  if (tenantSlug) {
    header['x-tenant-slug'] = tenantSlug
  }

  try {
    let refreshTask: ReturnType<typeof uni.request> | null = null
    const result = await withTimeout(
      new Promise<ApiResponse>((resolve, reject) => {
        refreshTask = uni.request({
          url: `${BASE_URL}/auth/refresh-token`,
          method: 'POST',
          header,
          data: { refresh_token: storedRefreshToken },
          timeout: 5000,  // ✅ 新增：5秒超时
          success: (res) => resolve(res.data as ApiResponse),
          fail: (err) => reject(err)
        })
      }),
      6000,  // ✅ 新增：Promise 总超时 6秒
      '刷新 Token 超时',
      () => refreshTask?.abort()
    )

    if (result.code === 0 || result.code === 200) {
      uni.setStorageSync('token', result.data.access_token)
      uni.setStorageSync('refresh_token', result.data.refresh_token)
      return true
    }
    return false
  } catch (error) {
    console.warn('刷新 Token 失败:', error)
    return false
  }
}

async function request<T>(
  url: string,
  method: 'GET' | 'POST' | 'PATCH' | 'DELETE' = 'GET',
  data?: any,
  headers?: any,
  showError: boolean = true,
  retryCount: number = 0
): Promise<ApiResponse<T>> {
  const token = uni.getStorageSync('token')
  let tenantSlug = uni.getStorageSync('tenant_slug')

  // 首次登录时，storage 中可能还没有 tenant_slug，尝试从请求 body 中获取
  if (!tenantSlug && data && typeof data === 'object' && data.tenant_slug) {
    tenantSlug = data.tenant_slug
  }

  const defaultHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
    ...(tenantSlug && { 'x-tenant-slug': tenantSlug })
  }

  const isLoginRequest = url.includes('/auth/login') || url.includes('/auth/wechat-login') || url.includes('/auth/wechat-auto-login') || url.includes('/auth/register') || url.includes('/auth/refresh-token')

  if (isLoginRequest) {
    hasLoggedOut = false
    isHandling401 = false
  }

  const requestTimeout = isLoginRequest ? 10000 : 30000
  const totalTimeout = requestTimeout + 2000  // ✅ Promise 总超时比请求超时多 2 秒

  let requestTask: ReturnType<typeof uni.request> | null = null

  return withTimeout(
    new Promise((resolve, reject) => {
      const fullUrl = `${BASE_URL}${url}`
      console.log(`API请求: ${method} ${fullUrl}`, data || '')

      requestTask = uni.request({
        url: fullUrl,
        method,
        data,
        header: { ...defaultHeaders, ...headers },
        timeout: requestTimeout,
        success: async (res) => {
          const result = res.data as ApiResponse<T>
          console.log(`API响应: ${method} ${url}`, res.statusCode, JSON.stringify(result))

          if (result.code === 401 && !isLoginRequest && retryCount === 0) {
            try {
              const refreshed = await refreshToken()
              if (refreshed) {
                const retryResult = await request(url, method, data, headers, showError, retryCount + 1)
                resolve(retryResult)
                return
              }
            } catch (retryError) {
              console.warn('重试失败:', retryError)
            }
          }

          if (result.code === 401) {
            if (isLoginRequest) {
              reject(new Error(result.msg || '登录失败'))
              return
            }

            if (isHandling401) {
              reject(new Error('登录已过期'))
              return
            }

            if (hasLoggedOut) {
              reject(new Error('登录已过期'))
              return
            }

            isHandling401 = true
            hasLoggedOut = true

            uni.removeStorageSync('token')
            uni.removeStorageSync('refresh_token')
            uni.removeStorageSync('user_role')
            uni.removeStorageSync('tenant_slug')
            uni.removeStorageSync('user_info')

            uni.showToast({ title: '登录已过期，请重新登录', icon: 'none' })

            setTimeout(() => {
              isHandling401 = false
              const pages = getCurrentPages()
              const currentPage = pages[pages.length - 1]
              if (currentPage && currentPage.route === 'pages/index/index') {
                hasLoggedOut = false
                return
              }
              uni.reLaunch({ url: '/pages/index/index' })
            }, 1000)

            reject(new Error('登录已过期'))
            return
          }

          if (result.code !== 0 && result.code !== 200 && showError) {
            uni.showToast({ title: result.msg || '请求失败', icon: 'none' })
          }
          resolve(result)
        },
        fail: (err) => {
          console.error(`API请求失败: ${method} ${url}`, JSON.stringify(err))
          if (showError) {
            const msg = isLoginRequest
              ? '登录失败，请检查网络连接'
              : '网络请求失败，请稍后重试'
            uni.showToast({ title: msg, icon: 'none' })
          }
          reject(err)
        }
      })
    }),
    totalTimeout,
    `请求超时: ${method} ${url}`,
    () => requestTask?.abort()
  )
}

export function resetAuthState() {
  hasLoggedOut = false
  isHandling401 = false
}

export const authApi = {
  login(data: { phone: string; password: string; tenant_slug: string }) {
    return request('/auth/login', 'POST', data, undefined, false)
  },

  register(data: { phone: string; nickname: string; tenant_slug: string; code?: string }) {
    return request('/auth/register', 'POST', data, undefined, false)
  },

  logout() {
    const refreshTokenValue = uni.getStorageSync('refresh_token')
    return request('/auth/logout', 'POST', { refresh_token: refreshTokenValue })
  },

  getMe() {
    return request('/auth/me')
  },

  wechatLogin(data: {
    bind_token: string
    phone?: string
    encrypted_data?: string
    iv?: string
    tenant_slug: string
  }) {
    return request('/auth/wechat-login', 'POST', data, undefined, false)
  },

  wxAutoLogin(data: { code: string; tenant_slug: string }) {
    return request('/auth/wechat-auto-login', 'POST', data, undefined, false)
  },

  sendSms(data: { phone: string; tenant_slug: string; type: string }) {
    return request('/auth/sms', 'POST', data, undefined, false)
  },

  /**
   * 绑定微信账号（新用户/未绑定时使用）
   */
  bindAccount(data: { 
    bind_token: string; 
    openid?: string;
    phone: string; 
    sms_code: string; 
    role?: 'student' | 'teacher';
    tenant_slug?: string 
  }) {
    return request('/auth/bind-account', 'POST', data, undefined, false)
  }
}

export const userApi = {
  updateProfile(userId: number, data: { nickname?: string; avatar_url?: string }) {
    return request(`/users/${userId}`, 'PATCH', data)
  },

  changePassword(userId: number, data: { old_password: string; new_password: string }) {
    return request(`/users/${userId}/password/change`, 'POST', data)
  },

  update(data: { nickname?: string; bio?: string }) {
    return request('/users/me', 'PATCH', data)
  }
}

export const courseApi = {
  list(params?: any) {
    const query = buildQuery(params)
    return request(`/courses${query}`)
  },

  get(id: number) {
    return request(`/courses/${id}`)
  },

  create(data: any) {
    return request('/courses/', 'POST', data)
  },

  update(id: number, data: any) {
    return request(`/courses/${id}`, 'PATCH', data)
  },

  delete(id: number) {
    return request(`/courses/${id}`, "DELETE")
  }
}

export const scheduleApi = {
  list(params?: any) {
    const query = buildQuery(params)
    return request(`/schedules${query}`)
  },

  get(id: number) {
    return request(`/schedules/${id}`)
  },

  create(data: any) {
    return request('/schedules/', 'POST', data)
  },

  update(id: number, data: any) {
    return request(`/schedules/${id}`, 'PATCH', data)
  },

  cancel(id: number) {
    return request(`/schedules/${id}/cancel`, 'POST')
  }
}

export const bookingApi = {
  list(params?: any) {
    const query = buildQuery(params)
    return request(`/bookings${query}`)
  },

  create(data: { schedule_id: number }) {
    return request('/bookings/', 'POST', data)
  },

  cancel(bookingId: number, reason?: string) {
    const query = reason ? `?reason=${encodeURIComponent(reason)}` : ''
    return request(`/bookings/${bookingId}/cancel${query}`, 'POST')
  },

  cancelBySchedule(scheduleId: number, reason?: string) {
    return request('/bookings/cancel', 'POST', { schedule_id: scheduleId, reason })
  },

  checkIn(bookingId: number) {
    return request(`/bookings/${bookingId}/check-in`, 'POST')
  },

  complete(bookingId: number) {
    return request(`/bookings/${bookingId}/complete`, 'POST')
  }
}

export const teacherApi = {
  getInfo() {
    return request('/teachers/me')
  },

  updateInfo(data: { title?: string; bio?: string; specialties?: string[] }) {
    return request('/teachers/me', 'PATCH', data)
  },

  getCourses(params?: any) {
    const query = buildQuery(params)
    return request(`/courses${query}`)
  },

  getSchedules(params?: any) {
    const query = buildQuery(params)
    return request(`/schedules${query}`)
  },

  getStats() {
    return request('/auth/me')
  }
}

export const studentApi = {
  getCourses(params?: any) {
    const query = buildQuery(params)
    return request(`/courses${query}`)
  },

  getStats() {
    return request('/auth/me')
  },

  getInfo() {
    return request('/users/me')
  },

  updateInfo(data: { nickname?: string; bio?: string }) {
    return request('/users/me', 'PATCH', data)
  }
}

export const classroomApi = {
  list(params?: any) {
    const query = buildQuery(params)
    return request(`/classrooms${query}`)
  }
}

export const aiChatApi = {
  chat(message: string, session_id: string = 'default') {
    return request('/ai/chat', 'POST', { message, session_id }, undefined, false)
  },

  getHistory(session_id: string = 'default') {
    const query = buildQuery({ session_id })
    return request(`/ai/history${query}`)
  },

  clearHistory(session_id: string = 'default') {
    return request(`/ai/history`, 'DELETE', { session_id })
  }
}