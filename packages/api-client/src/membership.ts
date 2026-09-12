import { apiClient, type ApiResponse } from './index'

export interface MembershipCardProduct {
  id: number
  public_id: string
  name: string
  card_type: string
  price: number
  total_credits: number | null
  validity_days: number | null
  applicable_course_ids: number[] | null
  applicable_course_type_codes: string[] | null
  max_weekly_usage: number | null
  description: string | null
  status: number
  sort_order: number
  created_at: string
  updated_at: string
}

export interface MembershipCardProductCreateParams {
  name: string
  card_type: string
  price: number
  total_credits?: number
  validity_days?: number
  applicable_course_type_codes: string[]
  applicable_course_ids?: number[]
  max_weekly_usage?: number
  description?: string
  sort_order?: number
}

export interface MembershipCardProductUpdateParams {
  name?: string
  price?: number
  total_credits?: number
  validity_days?: number
  applicable_course_ids?: number[]
  applicable_course_type_codes?: string[]
  max_weekly_usage?: number
  description?: string
  status?: number
  sort_order?: number
}

export interface MembershipCardProductListResponse {
  items: MembershipCardProduct[]
  total: number
  page: number
  page_size: number
}

export interface MembershipCard {
  id: number
  public_id: string
  student_id: number
  product_id: number | null
  card_type: string
  total_credits: number | null
  used_credits: number
  remaining_credits: number | null
  valid_from: string | null
  expire_at: string | null
  applicable_course_ids: number[] | null
  applicable_course_type_codes: string[] | null
  max_weekly_usage: number | null
  status: number
  frozen_reason: string | null
  created_at: string
  updated_at: string
  student_nickname?: string
  student_phone?: string
  product_name?: string
}

export interface MembershipCardListParams {
  page?: number
  page_size?: number
  student_id?: number
  product_id?: number
  card_type?: string
  status?: number
  keyword?: string
}

export interface MembershipCardCreateParams {
  student_id: number
  product_id?: number
  total_credits?: number
  validity_days?: number
  valid_from?: string
  applicable_course_ids?: number[]
  applicable_course_type_codes?: string[]
  max_weekly_usage?: number
  allow_duplicate?: boolean
  remark?: string
}

export interface MembershipCardFreezeParams {
  reason: string
  freeze_days: number
  auto_unfreeze?: boolean
}

export interface MembershipCardListResponse {
  items: MembershipCard[]
  total: number
  page: number
  page_size: number
}

export interface MembershipCardTransaction {
  id: number
  public_id: string
  card_id: number
  booking_id: number | null
  operation_type: string
  change_amount: number
  balance_after: number
  operator_id: number | null
  idempotency_key: string | null
  remark: string | null
  created_at: string
  updated_at: string
}

export interface MembershipCardTransactionListResponse {
  items: MembershipCardTransaction[]
  total: number
  page: number
  page_size: number
}

export const cardTypeApi = {
  list: (params?: any) =>
    apiClient.get<MembershipCardProductListResponse>('/membership/products', { params }),

  create: (data: MembershipCardProductCreateParams) =>
    apiClient.post<MembershipCardProduct>('/membership/products', data),

  update: (id: number, data: MembershipCardProductUpdateParams) =>
    apiClient.put<MembershipCardProduct>(`/membership/products/${id}`, data),

  remove: (id: number) =>
    apiClient.delete(`/membership/products/${id}`),

  listDeleted: (params?: { page?: number; page_size?: number }) =>
    apiClient.get<MembershipCardProductListResponse>('/membership/products/recycle-bin', { params }),

  restore: (id: number) =>
    apiClient.post<MembershipCardProduct>(`/membership/products/${id}/restore`),
}

export const membershipCardApi = {
  list: (params?: MembershipCardListParams) =>
    apiClient.get<MembershipCardListResponse>('/membership/cards', { params }),

  create: (data: MembershipCardCreateParams) =>
    apiClient.post<MembershipCard>('/membership/cards', data),

  get: (id: number) =>
    apiClient.get<MembershipCard>(`/membership/cards/${id}`),

  freeze: (id: number, data: MembershipCardFreezeParams) =>
    apiClient.post<MembershipCard>(`/membership/cards/${id}/freeze`, data),

  cancel: (id: number, data: { reason: string }) =>
    apiClient.post<MembershipCard>(`/membership/cards/${id}/cancel`, data),

  unfreeze: (id: number) =>
    apiClient.post<MembershipCard>(`/membership/cards/${id}/unfreeze`),

  activate: (id: number) =>
    apiClient.post<MembershipCard>(`/membership/cards/${id}/activate`),

  adminActivate: (id: number) =>
    apiClient.post<MembershipCard>(`/membership/cards/${id}/admin-activate`),

  getTransactions: (params?: { card_id?: number; page?: number; page_size?: number }) =>
    apiClient.get<MembershipCardTransactionListResponse>('/membership/transactions', { params }),
}