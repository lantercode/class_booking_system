import apiClient from './index'

export interface CourseType {
  id: number
  public_id: string
  tenant_id: number
  name: string
  code: string
  description: string | null
  required_card_types: string[] | null
  sort_order: number
  status: number
  min_students: number | null
  cancel_before_minutes: number | null
  created_at: string
  updated_at: string
}

export interface CourseTypeCreateParams {
  name: string
  code: string
  description?: string
  required_card_types?: string[]
  sort_order?: number
  status?: number
  min_students?: number
  cancel_before_minutes?: number
}

export interface CourseTypeUpdateParams {
  name?: string
  code?: string
  description?: string
  required_card_types?: string[]
  sort_order?: number
  status?: number
  min_students?: number
  cancel_before_minutes?: number
}

export interface Course {
  id: number
  public_id: string
  tenant_id: number
  name: string
  category: string | null
  course_type_code: string | null
  level: string | null
  cover_url: string | null
  description: string | null
  duration_minutes: number
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
  course_type_code?: string
}

export interface CourseCreateParams {
  name: string
  category?: string
  course_type_code: string
  level?: string
  cover_url?: string
  description?: string
  duration_minutes: number
  price?: number
  required_credits?: number
}

export interface CourseUpdateParams {
  name?: string
  category?: string
  course_type_code?: string
  level?: string
  cover_url?: string
  description?: string
  duration_minutes?: number
  price?: number
  required_credits?: number
  status?: number
}

export interface CourseCategory {
  id: number
  public_id: string
  tenant_id: number
  name: string
  code: string
  description: string | null
  icon_url: string | null
  sort_order: number
  status: number
  course_count: number
  created_at: string
  updated_at: string
}

export interface CourseCategoryCreateParams {
  name: string
  code: string
  description?: string
  icon_url?: string
  sort_order?: number
  status?: number
}

export interface CourseCategoryUpdateParams {
  name?: string
  code?: string
  description?: string
  icon_url?: string
  sort_order?: number
  status?: number
}

export interface CourseListResponse {
  total: number
  page: number
  page_size: number
  items: Course[]
}

export const courseTypeApi = {
  list(params?: { status?: number }) {
    return apiClient.get<CourseType[]>('/courses/types', { params })
  },

  getById(id: number) {
    return apiClient.get<CourseType>(`/courses/types/${id}`)
  },

  create(data: CourseTypeCreateParams) {
    return apiClient.post<CourseType>('/courses/types', data)
  },

  update(id: number, data: CourseTypeUpdateParams) {
    return apiClient.patch<CourseType>(`/courses/types/${id}`, data)
  },

  remove(id: number) {
    return apiClient.delete(`/courses/types/${id}`)
  },
}

export const courseApi = {
  list(params?: CourseListParams) {
    return apiClient.get<CourseListResponse>('/courses', { params })
  },

  getById(id: number) {
    return apiClient.get<Course>(`/courses/${id}`)
  },

  create(data: CourseCreateParams) {
    return apiClient.post<Course>('/courses/', data)
  },

  update(id: number, data: CourseUpdateParams) {
    return apiClient.patch<Course>(`/courses/${id}`, data)
  },

  remove(id: number) {
    return apiClient.delete(`/courses/${id}`)
  },
}

export const courseCategoryApi = {
  list(params?: { status?: number }) {
    return apiClient.get<{ total: number; items: CourseCategory[] }>('/courses/categories', {
      params,
    })
  },

  getById(id: number) {
    return apiClient.get<CourseCategory>(`/courses/categories/${id}`)
  },

  create(data: CourseCategoryCreateParams) {
    return apiClient.post<CourseCategory>('/courses/categories', data)
  },

  update(id: number, data: CourseCategoryUpdateParams) {
    return apiClient.patch<CourseCategory>(`/courses/categories/${id}`, data)
  },

  remove(id: number) {
    return apiClient.delete(`/courses/categories/${id}`)
  },
}