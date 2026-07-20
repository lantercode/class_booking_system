import apiClient from './index'

export interface Course {
  id: number
  public_id: string
  tenant_id: number
  name: string
  category: string | null
  level: string | null
  cover_url: string | null
  description: string | null
  duration_minutes: number
  max_capacity: number
  price: number
  required_credits: number
  status: number
  created_at: string
  updated_at: string
}

export interface CourseListParams {
  page?: number
  page_size?: number
  keyword?: string
  category?: string
  level?: string
  status?: number
}

export interface CourseCreateParams {
  name: string
  category?: string
  level?: string
  cover_url?: string
  description?: string
  duration_minutes: number
  max_capacity: number
  price?: number
  required_credits?: number
}

export interface CourseUpdateParams {
  name?: string
  category?: string
  level?: string
  cover_url?: string
  description?: string
  duration_minutes?: number
  max_capacity?: number
  price?: number
  required_credits?: number
  status?: number
}

export interface CourseListResponse {
  total: number
  page: number
  page_size: number
  items: Course[]
}

export const courseApi = {
  list(params?: CourseListParams) {
    return apiClient.get<CourseListResponse>('/courses', { params })
  },

  getById(id: number) {
    return apiClient.get<Course>(`/courses/${id}`)
  },

  create(data: CourseCreateParams) {
    return apiClient.post<Course>('/courses', data)
  },

  update(id: number, data: CourseUpdateParams) {
    return apiClient.patch<Course>(`/courses/${id}`, data)
  },

  remove(id: number) {
    return apiClient.delete(`/courses/${id}`)
  },
}
