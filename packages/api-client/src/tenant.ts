import apiClient from './index'

// ============================================================
// 租户配置（settings）
// ============================================================

export interface TenantSettings {
  /** 预约可提前取消的最少分钟数（1-480）；超出此窗口取消将影响课时 */
  booking_cancel_minutes: number
  /** 预约可提前的最大天数（1-90） */
  booking_advance_days: number
}

/**
 * 更新租户配置入参。
 * 两个字段均为可选：仅传递需要修改的键，后端使用 exclude_unset 做浅合并。
 */
export interface TenantSettingsUpdate {
  booking_cancel_minutes?: number
  booking_advance_days?: number
}

// ============================================================
// 租户基本信息（info）
// ============================================================

export interface TenantInfo {
  id: number
  name: string
  /** 租户 slug，不可修改，用于登录与 API 访问 */
  slug: string
  logo_url: string | null
  contact_phone: string | null
  contact_email: string | null
}

/**
 * 更新租户基本信息入参。
 * name 必填；其余字段仅当需要修改时传入。
 */
export interface TenantInfoUpdate {
  name: string
  logo_url?: string
  contact_phone?: string
  contact_email?: string
}

export const tenantApi = {
  /** 获取当前租户配置 */
  getSettings() {
    return apiClient.get<TenantSettings>('/tenant/settings')
  },

  /** 更新当前租户配置（浅合并：仅修改显式提交的字段） */
  updateSettings(data: TenantSettingsUpdate) {
    return apiClient.put<TenantSettings>('/tenant/settings', data)
  },

  /** 获取当前租户基本信息 */
  getInfo() {
    return apiClient.get<TenantInfo>('/tenant/info')
  },

  /** 更新当前租户基本信息 */
  updateInfo(data: TenantInfoUpdate) {
    return apiClient.put<TenantInfo>('/tenant/info', data)
  },
}
