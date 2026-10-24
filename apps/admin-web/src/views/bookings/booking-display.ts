import type { Booking } from '@dance-saas/api-client'

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '-'
  const d = new Date(iso)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${day} ${hh}:${mm}`
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${hh}:${mm}`
}

export function formatDateTimeRange(start: string | null | undefined, end: string | null | undefined): string {
  if (!start) return '-'
  const endStr = end ? formatTime(end) : ''
  return `${formatDateTime(start)}${endStr ? ` - ${endStr}` : ''}`
}

/** 签到时间短格式：MM-dd HH:mm（完整时间用 formatDateTime） */
export function formatShortDateTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${m}-${day} ${hh}:${mm}`
}

export function statusTagText(row: Booking): string {
  if (row.status === 5) return '未到场'
  switch (row.display_status) {
    case 1:
      return '已预约'
    case 2:
      return '已取消'
    case 3:
      return '已签到'
    case 4:
      return '已完成'
    default:
      break
  }
  switch (row.status) {
    case 1:
      return '已预约'
    case 2:
      return '已取消'
    case 3:
      return '已签到'
    case 4:
      return '已完成'
    default:
      return '未知'
  }
}

export type StatusTagType = 'warning' | 'info' | 'primary' | 'success' | 'danger'

export function statusTagType(row: Booking): StatusTagType {
  if (row.status === 5) return 'danger'
  switch (row.display_status) {
    case 1:
      return 'primary'
    case 2:
      return 'info'
    case 3:
      return 'primary'
    case 4:
      return 'success'
    default:
      break
  }
  switch (row.status) {
    case 1:
      return 'primary'
    case 2:
      return 'info'
    case 3:
      return 'primary'
    case 4:
      return 'success'
    default:
      return 'info'
  }
}

export function cardStatusTagText(row: Booking): string {
  if (row.card_type === 'count' && row.remaining_credits === 0) return '已用尽'
  switch (row.card_status) {
    case 0:
      return '未激活'
    case 1:
      return '使用中'
    case 2:
      return '已过期'
    case 3:
      return '已冻结'
    case 6:
      return '已作废'
    default:
      return '未知'
  }
}

export type CardStatusTagType = 'success' | 'warning' | 'info' | 'primary' | 'danger'

export function cardStatusTagType(row: Booking): CardStatusTagType {
  if (row.card_type === 'count' && row.remaining_credits === 0) return 'warning'
  switch (row.card_status) {
    case 0:
      return 'info'
    case 1:
      return 'success'
    case 2:
      return 'info'
    case 3:
      return 'primary'
    case 6:
      return 'danger'
    default:
      return 'info'
  }
}

export function sourceText(source: string): string {
  switch (source) {
    case 'self':
      return '本人'
    case 'admin':
      return '管理员'
    case 'teacher':
      return '教师'
    default:
      return source || '—'
  }
}

/** P-A6 代签到确认弹窗中的卡状态异常提示（过期/冻结/作废）：返回空串表示无异常 */
export function cardAbnormalStatusText(cardStatus: number | null | undefined): string {
  switch (cardStatus) {
    case 2:
      return '已过期'
    case 3:
      return '已冻结'
    case 6:
      return '已作废'
    default:
      return ''
  }
}

/** 行样式：计划卡失效红底 */
export function rowCardInvalidClassName({ row }: { row: Booking }): string {
  if (row.card_status === 6 || row.card_status === 2) return 'row-card-invalid'
  return ''
}
