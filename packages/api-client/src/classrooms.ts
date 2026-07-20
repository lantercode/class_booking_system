import apiClient from './index'

export interface Classroom {
  id: number
  tenant_id: number
  name: string
  capacity: number
  equipment: string[]
  status: number
  created_at: string
  updated_at: string
}

export interface ClassroomListParams {
  page?: number
  page_size?: number
  keyword?: string
  status?: number
}

export interface ClassroomCreateParams {
  name: string
  capacity: number
  equipment?: string[]
}

export interface ClassroomUpdateParams {
  name?: string
  capacity?: number
  equipment?: string[]
  status?: number
}

export interface ClassroomListResponse {
  total: number
  page: number
  page_size: number
  items: Classroom[]
}

export const classroomApi = {
  list(params?: ClassroomListParams) {
    return apiClient.get<ClassroomListResponse>('/classrooms', { params })
  },

  getById(id: number) {
    return apiClient.get<Classroom>(`/classrooms/${id}`)
  },

  create(data: ClassroomCreateParams) {
    return apiClient.post<Classroom>('/classrooms', data)
  },

  update(id: number, data: ClassroomUpdateParams) {
    return apiClient.patch<Classroom>(`/classrooms/${id}`, data)
  },

  remove(id: number) {
    return apiClient.delete(`/classrooms/${id}`)
  },
}
