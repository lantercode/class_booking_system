import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'

export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
}

export interface ApiError {
  code: number
  message: string
  detail?: string
}

const TOKEN_KEY = 'token'
const REFRESH_TOKEN_KEY = 'refreshToken'
const API_BASE = '/api/v1'

class ApiClient {
  private instance: AxiosInstance

  constructor() {
    this.instance = axios.create({
      baseURL: API_BASE,
      timeout: 15000,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    this.setupRequestInterceptor()
    this.setupResponseInterceptor()
  }

  private setupRequestInterceptor() {
    this.instance.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        const token = localStorage.getItem(TOKEN_KEY)
        if (token && config.headers) {
          config.headers.Authorization = `Bearer ${token}`
        }

        const tenantId = localStorage.getItem('tenantId')
        if (tenantId && config.headers) {
          config.headers['x-tenant-id'] = tenantId
        }

        return config
      },
      (error) => Promise.reject(error)
    )
  }

  private setupResponseInterceptor() {
    this.instance.interceptors.response.use(
      (response: AxiosResponse<ApiResponse>) => {
        return response
      },
      async (error) => {
        const originalRequest = error.config

        if (error.response?.status === 401 && !originalRequest._retry) {
          const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY)

          if (refreshToken) {
            originalRequest._retry = true
            try {
              const res = await axios.post(`${API_BASE}/auth/refresh-token`, {
                refresh_token: refreshToken,
              })

              const { access_token, refresh_token } = res.data.data
              localStorage.setItem(TOKEN_KEY, access_token)
              localStorage.setItem(REFRESH_TOKEN_KEY, refresh_token)

              originalRequest.headers.Authorization = `Bearer ${access_token}`
              return this.instance(originalRequest)
            } catch {
              this.clearAuth()
            }
          } else {
            this.clearAuth()
          }
        }

        return Promise.reject(error)
      }
    )
  }

  private clearAuth() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
    window.location.href = '/login'
  }

  async get<T = any>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    const response = await this.instance.get<ApiResponse<T>>(url, config)
    return response.data
  }

  async post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    const response = await this.instance.post<ApiResponse<T>>(url, data, config)
    return response.data
  }

  async put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    const response = await this.instance.put<ApiResponse<T>>(url, data, config)
    return response.data
  }

  async patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    const response = await this.instance.patch<ApiResponse<T>>(url, data, config)
    return response.data
  }

  async delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    const response = await this.instance.delete<ApiResponse<T>>(url, config)
    return response.data
  }

  getAxiosInstance(): AxiosInstance {
    return this.instance
  }
}

export const apiClient = new ApiClient()
export default apiClient