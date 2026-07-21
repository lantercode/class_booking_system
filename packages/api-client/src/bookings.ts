import apiClient from './index'

export interface Booking {
  id: number
  public_id: string
  tenant_id: number
  schedule_id: number
  student_id: number
  status: number
  source: string
  membership_card_id: number | null
  booked_at: string
  cancelled_at: string | null
  cancelled_reason: string | null
  checked_in_at: string | null
  created_at: string
  updated_at: string
  student_nickname?: string | null
  student_phone?: string | null
}

export interface BookingListParams {
  page?: number
  page_size?: number
  schedule_id?: number
  student_id?: number
  status?: number
}

export interface BookingCreateParams {
  schedule_id: number
  source?: string
  membership_card_id?: number
}

export interface BookingListResponse {
  total: number
  page: number
  page_size: number
  items: Booking[]
}

export const bookingApi = {
  list(params?: BookingListParams) {
    return apiClient.get<BookingListResponse>('/bookings', { params })
  },

  getById(id: number) {
    return apiClient.get<Booking>(`/bookings/${id}`)
  },

  create(data: BookingCreateParams) {
    return apiClient.post<Booking>('/bookings', data)
  },

  cancel(scheduleId: number, data?: { reason?: string }) {
    return apiClient.post<Booking>(`/bookings/cancel`, { schedule_id: scheduleId, reason: data?.reason })
  },

  checkIn(id: number) {
    return apiClient.post<Booking>(`/bookings/${id}/check-in`)
  },

  complete(id: number) {
    return apiClient.post<Booking>(`/bookings/${id}/complete`)
  },
}