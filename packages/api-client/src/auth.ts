import { apiClient } from './index'

export interface CurrentUserResponse {
  id: number
  phone: string
  nickname: string
  avatar: string | null
  gender: string | null
  status: number
  roles: string[]
  created_at: string
}

export interface UpdateCurrentUserParams {
  nickname?: string
  avatar_url?: string
}

export const authApi = {
  /** 获取当前用户信息 */
  getMe() {
    return apiClient.get<CurrentUserResponse>('/auth/me')
  },

  /** 更新当前用户信息（仅 nickname / avatar_url） */
  patchMe(data: UpdateCurrentUserParams) {
    return apiClient.patch<CurrentUserResponse>('/auth/me', data)
  },
}
