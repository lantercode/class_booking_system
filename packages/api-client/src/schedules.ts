import apiClient from './index'

export interface Schedule {
  id: number
  public_id: string
  tenant_id: number
  course_id: number
  teacher_id: number
  classroom_id: number | null
  start_at: string
  end_at: string
  capacity: number
  booked_count: number
  booking_opens_at: string | null
  booking_closes_at: string | null
  cancel_deadline: string | null
  status: number
  notes: string | null
  created_at: string
  updated_at: string
  teacher_name?: string | null
  classroom_name?: string | null
}

export interface ScheduleListParams {
  page?: number
  page_size?: number
  course_id?: number
  teacher_id?: number
  classroom_id?: number
  status?: number
  start_from?: string
  start_to?: string
}

export interface ScheduleCreateParams {
  course_id: number
  teacher_id: number
  classroom_id?: number
  start_at: string
  end_at: string
  capacity: number
  booking_opens_at?: string
  booking_closes_at?: string
  cancel_deadline?: string
  notes?: string
}

export interface ScheduleUpdateParams {
  teacher_id?: number
  classroom_id?: number
  start_at?: string
  end_at?: string
  capacity?: number
  booking_opens_at?: string
  booking_closes_at?: string
  cancel_deadline?: string
  status?: number
  notes?: string
}

export interface ScheduleListResponse {
  total: number
  page: number
  page_size: number
  items: Schedule[]
}

export const scheduleApi = {
  list(params?: ScheduleListParams) {
    return apiClient.get<ScheduleListResponse>('/schedules', { params })
  },

  getById(id: number) {
    return apiClient.get<Schedule>(`/schedules/${id}`)
  },

  create(data: ScheduleCreateParams) {
    return apiClient.post<Schedule>('/schedules', data)
  },

  batchCreate(items: ScheduleCreateParams[]) {
    return apiClient.post<Schedule[]>('/schedules/batch', items)
  },

  update(id: number, data: ScheduleUpdateParams) {
    return apiClient.patch<Schedule>(`/schedules/${id}`, data)
  },

  cancel(id: number) {
    return apiClient.post<Schedule>(`/schedules/${id}/cancel`)
  },

  delete(id: number) {
    return apiClient.delete(`/schedules/${id}`)
  },
}