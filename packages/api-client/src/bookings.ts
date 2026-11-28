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
  course_name?: string | null
  start_at?: string | null
  end_at?: string | null
  classroom_name?: string | null
  teacher_name?: string | null
  display_status?: number
  card_no?: string | null
  card_status?: number | null
  card_type?: string | null
  remaining_credits?: number | null
}

export interface BookingListParams {
  page?: number
  page_size?: number
  schedule_id?: number
  student_id?: number
  status?: string | number
  display_status?: number
  /** 仅查询未开始的排期（学员端"待上课"语义）；不传则按状态全量查询 */
  upcoming?: boolean
  keyword?: string
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

/**
 * 生成 UUID v4 形式的幂等键。
 * 优先使用 `crypto.randomUUID()`；在仅支持 `getRandomValues` 的环境
 * （非安全上下文）退化为标准 v4 字节拼装，仍保证随机性与唯一性。
 */
export function generateIdempotencyKey(): string {
  const cryptoObj = typeof globalThis !== 'undefined' ? (globalThis as any).crypto : undefined

  if (typeof cryptoObj?.randomUUID === 'function') {
    return cryptoObj.randomUUID()
  }

  if (typeof cryptoObj?.getRandomValues === 'function') {
    const bytes: Uint8Array = cryptoObj.getRandomValues(new Uint8Array(16))
    bytes[6] = (bytes[6] & 0x0f) | 0x40
    bytes[8] = (bytes[8] & 0x3f) | 0x80
    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
  }

  throw new Error('generateIdempotencyKey: 当前环境不支持安全随机数')
}

/**
 * 幂等键生命周期管理。
 *
 * - `acquire(signature)`：同一提交意图（signature 相同）在未拿到响应前复用同一 key；
 * - `release(signature)`：拿到任意服务端响应（成功或业务错误）后丢弃 key，
 *   确保下一次提交生成新 key（避免取消后重新预约被重放成旧预约）。
 *
 * 不要在收到响应后继续按 payload 缓存 key。
 */
export function createIdempotencyKeyStore(generate: () => string = generateIdempotencyKey) {
  const pending = new Map<string, string>()

  return {
    acquire(signature: string): string {
      const existing = pending.get(signature)
      if (existing) return existing
      const key = generate()
      pending.set(signature, key)
      return key
    },
    release(signature: string): void {
      pending.delete(signature)
    },
  }
}

export const bookingApi = {
  list(params?: BookingListParams) {
    return apiClient.get<BookingListResponse>('/bookings', { params })
  },

  getById(id: number) {
    return apiClient.get<Booking>(`/bookings/${id}`)
  },

  /**
   * 创建预约。
   *
   * @param idempotencyKey 可选幂等键，经 `Idempotency-Key` 请求头上送（不进请求体）。
   *   同一 key + 相同参数重试：后端返回首次创建的预约（HTTP 200），不会重复扣次；
   *   同一 key + 不同参数：后端返回 409。
   */
  create(data: BookingCreateParams, idempotencyKey?: string) {
    return apiClient.post<Booking>('/bookings/', data, {
      headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined,
    })
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

  adminCancel(id: number, reason?: string) {
    return apiClient.post<Booking>(`/bookings/${id}/admin-cancel`, null, { params: reason ? { reason } : {} })
  },
}