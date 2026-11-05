import apiClient from './index'

export interface TeacherInfo {
  user_id: number
  nickname: string
  phone: string
  avatar: string | null
  title: string | null
  intro: string | null
  specialties: string[] | null
  years_of_experience: number | null
}

export interface TeacherUpdateParams {
  nickname?: string
  intro?: string
  bio?: string
  avatar?: string
  title?: string
  specialties?: string[]
  years_of_experience?: number
}

export const teacherApi = {
  getInfo() {
    return apiClient.get<TeacherInfo>('/teachers/me')
  },

  updateInfo(data: TeacherUpdateParams) {
    return apiClient.patch<TeacherInfo>('/teachers/me', data)
  },

  /** 管理端：更新指定教师的资料（简介等） */
  update(userId: number, data: TeacherUpdateParams) {
    return apiClient.patch<TeacherInfo>(`/teachers/${userId}`, data)
  },
}