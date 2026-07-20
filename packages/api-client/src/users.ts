import apiClient from './index'

export interface User {
  id: number
  tenant_id: number
  phone: string
  nickname: string | null
  avatar_url: string | null
  gender: number | null
  birthday: string | null
  status: number
  roles: string[]
  created_at: string
  updated_at: string
}

export interface UserListParams {
  page?: number
  page_size?: number
  keyword?: string
  role_code?: string
  status?: number
}

export interface UserListResponse {
  total: number
  page: number
  page_size: number
  items: User[]
}

export interface UserCreateParams {
  phone: string
  password: string
  nickname?: string
  gender?: number
  role_codes?: string[]
}

export interface UserUpdateParams {
  nickname?: string
  avatar_url?: string
  gender?: number
  birthday?: string
  status?: number
  role_ids?: number[]
}

export interface UserRoleUpdateParams {
  role_ids: number[]
}

export const userApi = {
  list(params?: UserListParams) {
    return apiClient.get<UserListResponse>('/users', { params })
  },

  getById(id: number) {
    return apiClient.get<User>(`/users/${id}`)
  },

  create(data: UserCreateParams) {
    return apiClient.post<User>('/users', data)
  },

  update(id: number, data: UserUpdateParams) {
    return apiClient.patch<User>(`/users/${id}`, data)
  },

  updateRoles(id: number, data: UserRoleUpdateParams) {
    return apiClient.put(`/users/${id}/roles`, data)
  },

  resetPassword(id: number, newPassword: string) {
    return apiClient.post(`/users/${id}/password/reset`, { new_password: newPassword })
  },

  delete(id: number) {
    return apiClient.delete(`/users/${id}`)
  },
}