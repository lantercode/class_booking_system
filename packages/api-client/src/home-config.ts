import apiClient from './index'

export type HomeConfigModuleType = 'banner' | 'teachers' | 'courses' | 'video'

/** banner 轮播项 */
export interface BannerModuleItem {
  id?: string
  title?: string
  subtitle?: string
  image_url?: string
  link_url?: string
}

/** 舞蹈视频项（和 banner 一样支持多个） */
export interface VideoModuleItem {
  id?: string
  title?: string
  description?: string
  cover_url?: string
  video_url: string  // 必填：上传后存 object_key，或外部 URL
}

/** teachers 模块配置（从教师列表选） */
export interface TeachersModuleConfig {
  display_count?: number  // 旧草稿兼容，前端不再展示
  teacher_ids: number[]
}

/** courses 模块配置（从课程列表选） */
export interface CoursesModuleConfig {
  display_count?: number  // 旧草稿兼容，前端不再展示
  sort_by?: 'latest' | 'popular' | 'recommended'  // 旧草稿兼容
  course_ids: number[]
}

export interface HomeConfigModule {
  type: HomeConfigModuleType
  enabled: boolean
  sort: number
  // banner / video 用 items[]（支持多轮播、多视频）
  items?: BannerModuleItem[] | VideoModuleItem[]
  // teachers / courses 用 config（引用现有实体 ID）
  config?: TeachersModuleConfig | CoursesModuleConfig
}

export interface HomeConfigPayload {
  schema_version: number
  modules: HomeConfigModule[]
}

export interface HomeConfigDraftResponse {
  id: number
  tenant_id: number
  scope: string
  version: number
  payload: HomeConfigPayload
  published_at: string | null
  operator_id: number | null
  created_at: string
  updated_at: string
  /** draft 是否与最新 published 不同 */
  has_changes?: boolean
}

export interface HomeConfigVersionItem {
  id: number
  version: number
  published_at: string | null
  operator_id: number | null
  created_at: string
}

export interface HomeConfigVersionsResponse {
  items: HomeConfigVersionItem[]
  total: number
}

export interface HomeConfigPublishedResponse {
  id: number
  version: number
  payload: HomeConfigPayload
  published_at: string | null
}

export const homeConfigApi = {
  /** 读取 draft（不存在则后端自动创建空 draft） */
  getHomeConfigDraft() {
    return apiClient.get<HomeConfigDraftResponse>('/home-config/draft')
  },

  /** 整体覆盖 draft payload */
  updateHomeConfigDraft(payload: HomeConfigPayload) {
    return apiClient.put<HomeConfigDraftResponse>('/home-config/draft', { payload })
  },

  /** 发布 draft 为新版本 */
  publishHomeConfig() {
    return apiClient.post<HomeConfigPublishedResponse>('/home-config/publish')
  },

  /** 读取最新已发布配置 */
  getHomeConfigPublished() {
    return apiClient.get<HomeConfigPublishedResponse>('/home-config/published')
  },

  /** 列出已发布版本 */
  listHomeConfigVersions() {
    return apiClient.get<HomeConfigVersionsResponse>('/home-config/versions')
  },
}
