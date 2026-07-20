import apiClient from './index'

export interface Role {
  id: number
  tenant_id: number
  code: string
  name: string
  is_system: boolean
  description: string | null
  created_at: string
  updated_at: string
}

export interface Permission {
  id: number
  code: string
  name: string
  module: string
  description: string | null
}

export interface RoleListParams {
  page?: number
  page_size?: number
}

export interface RoleListResponse {
  total: number
  page: number
  page_size: number
  items: Role[]
}

export interface PermissionListResponse {
  total: number
  items: Permission[]
}

export const roleApi = {
   create(data: { code: string; name: string; description?: string; permission_ids?: number[] }) {
    return apiClient.post<Role>('/roles', data)
  },

  list(params?: RoleListParams) {
    return apiClient.get<RoleListResponse>('/roles', { params })
  },

  getById(id: number) {
    return apiClient.get<Role>(`/roles/${id}`)
  },

  getPermissions(roleId: number) {
    return apiClient.get<PermissionListResponse>(`/roles/${roleId}/permissions`)
  },

  assignPermissions(roleId: number, permissionIds: number[]) {
    return apiClient.put(`/roles/${roleId}/permissions`, {
      permission_ids: permissionIds,
    })
  },

  listPermissions(module?: string) {
    return apiClient.get<PermissionListResponse>('/roles/permissions', {
      params: module ? { module } : undefined,
    })
  },

  delete(id: number) {
    return apiClient.delete(`/roles/${id}`)
  },
}