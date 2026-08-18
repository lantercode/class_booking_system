const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

function padZero(num: number): string {
  return String(num).padStart(2, '0')
}

export function formatDate(dateTimeStr: string | Date | null | undefined, showWeekday: boolean = false): string {
  // ✅ 安全检查：防止 undefined/null 导致 TypeError
  if (dateTimeStr === null || dateTimeStr === undefined || dateTimeStr === '') {
    console.warn('⚠️ formatDate - 收到空值:', dateTimeStr)
    return '日期待定'
  }

  try {
    const date = typeof dateTimeStr === 'string' ? new Date(dateTimeStr) : dateTimeStr

    // ✅ 检查日期是否有效
    if (!(date instanceof Date) || isNaN(date.getTime())) {
      console.warn('⚠️ formatDate - 无效日期:', dateTimeStr, '→ 解析结果:', date)
      return '日期待定'
    }

    const month = date.getMonth() + 1
    const day = date.getDate()

    let result = `${month}月${day}日`

    if (showWeekday) {
      result += ` ${WEEKDAYS[date.getDay()]}`
    }

    return result
  } catch (error) {
    console.error('❌ formatDate - 解析异常:', error, '输入值:', dateTimeStr)
    return '日期待定'
  }
}

export function formatTime(dateTimeStr: string | Date | null | undefined): string {
  // ✅ 安全检查：防止 undefined/null 导致 TypeError
  if (dateTimeStr === null || dateTimeStr === undefined || dateTimeStr === '') {
    console.warn('⚠️ formatTime - 收到空值:', dateTimeStr)
    return '时间待定'
  }

  try {
    const date = typeof dateTimeStr === 'string' ? new Date(dateTimeStr) : dateTimeStr

    // ✅ 检查日期是否有效
    if (!(date instanceof Date) || isNaN(date.getTime())) {
      console.warn('⚠️ formatTime - 无效日期:', dateTimeStr, '→ 解析结果:', date)
      return '时间待定'
    }

    const hours = padZero(date.getHours())
    const minutes = padZero(date.getMinutes())

    return `${hours}:${minutes}`
  } catch (error) {
    console.error('❌ formatTime - 解析异常:', error, '输入值:', dateTimeStr)
    return '时间待定'
  }
}

export function formatDateTime(dateTimeStr: string | Date | null | undefined, options?: { showWeekday?: boolean; showSeconds?: boolean }): string {
  // ✅ 安全检查：防止 undefined/null 导致 TypeError
  if (dateTimeStr === null || dateTimeStr === undefined || dateTimeStr === '') {
    console.warn('⚠️ formatDateTime - 收到空值:', dateTimeStr)
    return '时间待定'
  }

  try {
    const date = typeof dateTimeStr === 'string' ? new Date(dateTimeStr) : dateTimeStr

    // ✅ 检查日期是否有效
    if (!(date instanceof Date) || isNaN(date.getTime())) {
      console.warn('⚠️ formatDateTime - 无效日期:', dateTimeStr, '→ 解析结果:', date)
      return '时间待定'
    }

    const month = date.getMonth() + 1
    const day = date.getDate()
    const hours = padZero(date.getHours())
    const minutes = padZero(date.getMinutes())
    const seconds = options?.showSeconds ? `:${padZero(date.getSeconds())}` : ''

    let result = `${month}月${day}日 ${hours}:${minutes}${seconds}`

    if (options?.showWeekday) {
      result += ` (${WEEKDAYS[date.getDay()]})`
    }

    return result
  } catch (error) {
    console.error('❌ formatDateTime - 解析异常:', error, '输入值:', dateTimeStr)
    return '时间待定'
  }
}

export function formatRelativeTime(dateTimeStr: string | Date | null | undefined): string {
  // ✅ 安全检查：防止 undefined/null 导致 TypeError
  if (dateTimeStr === null || dateTimeStr === undefined || dateTimeStr === '') {
    console.warn('⚠️ formatRelativeTime - 收到空值:', dateTimeStr)
    return '未知时间'
  }

  try {
    const date = typeof dateTimeStr === 'string' ? new Date(dateTimeStr) : dateTimeStr

    // ✅ 检查日期是否有效
    if (!(date instanceof Date) || isNaN(date.getTime())) {
      console.warn('⚠️ formatRelativeTime - 无效日期:', dateTimeStr, '→ 解析结果:', date)
      return '未知时间'
    }

    const now = new Date()
    const diff = now.getTime() - date.getTime()

    if (diff < 0) {
      return '刚刚'
    }

    const seconds = Math.floor(diff / 1000)
    const minutes = Math.floor(seconds / 60)
    const hours = Math.floor(minutes / 60)
    const days = Math.floor(hours / 24)
  
  if (seconds < 60) {
    return '刚刚'
  }
  
  if (minutes < 60) {
    return `${minutes}分钟前`
  }
  
  if (hours < 24) {
    return `${hours}小时前`
  }
  
  if (days < 7) {
    return `${days}天前`
  }
  
  if (days < 30) {
    const weeks = Math.floor(days / 7)
    return `${weeks}周前`
  }
  
  if (days < 365) {
    const months = Math.floor(days / 30)
    return `${months}个月前`
  }

  const years = Math.floor(days / 365)
  return `${years}年前`
  } catch (error) {
    console.error('❌ formatRelativeTime - 解析异常:', error, '输入值:', dateTimeStr)
    return '未知时间'
  }
}

export function formatFullDate(dateTimeStr: string | Date | null | undefined): string {
  // ✅ 安全检查：防止 undefined/null 导致 TypeError
  if (dateTimeStr === null || dateTimeStr === undefined || dateTimeStr === '') {
    console.warn('⚠️ formatFullDate - 收到空值:', dateTimeStr)
    return '日期待定'
  }

  try {
    const date = typeof dateTimeStr === 'string' ? new Date(dateTimeStr) : dateTimeStr

    // ✅ 检查日期是否有效
    if (!(date instanceof Date) || isNaN(date.getTime())) {
      console.warn('⚠️ formatFullDate - 无效日期:', dateTimeStr, '→ 解析结果:', date)
      return '日期待定'
    }

    const year = date.getFullYear()
    const month = padZero(date.getMonth() + 1)
    const day = padZero(date.getDate())

    return `${year}-${month}-${day}`
  } catch (error) {
    console.error('❌ formatFullDate - 解析异常:', error, '输入值:', dateTimeStr)
    return '日期待定'
  }
}

export function formatISODate(dateTimeStr: string | Date | null | undefined): string {
  // ✅ 安全检查：防止 undefined/null 导致 TypeError
  if (dateTimeStr === null || dateTimeStr === undefined || dateTimeStr === '') {
    console.warn('⚠️ formatISODate - 收到空值:', dateTimeStr)
    return ''
  }

  try {
    const date = typeof dateTimeStr === 'string' ? new Date(dateTimeStr) : dateTimeStr

    // ✅ 检查日期是否有效
    if (!(date instanceof Date) || isNaN(date.getTime())) {
      console.warn('⚠️ formatISODate - 无效日期:', dateTimeStr, '→ 解析结果:', date)
      return ''
    }

    return date.toISOString().split('T')[0]
  } catch (error) {
    console.error('❌ formatISODate - 解析异常:', error, '输入值:', dateTimeStr)
    return ''
  }
}

export function isToday(dateTimeStr: string | Date | null | undefined): boolean {
  // ✅ 安全检查
  if (dateTimeStr === null || dateTimeStr === undefined || dateTimeStr === '') {
    return false
  }

  try {
    const date = typeof dateTimeStr === 'string' ? new Date(dateTimeStr) : dateTimeStr

    // ✅ 检查日期是否有效
    if (!(date instanceof Date) || isNaN(date.getTime())) {
      return false
    }

    const today = new Date()
  
  return (
    date.getFullYear() === today.getFullYear() &&
    date.getMonth() === today.getMonth() &&
    date.getDate() === today.getDate()
  )
  } catch (error) {
    console.error('❌ isToday - 解析异常:', error)
    return false
  }
}

export function isFuture(dateTimeStr: string | Date | null | undefined): boolean {
  // ✅ 安全检查
  if (dateTimeStr === null || dateTimeStr === undefined || dateTimeStr === '') {
    return false
  }

  try {
    const date = typeof dateTimeStr === 'string' ? new Date(dateTimeStr) : dateTimeStr

    // ✅ 检查日期是否有效
    if (!(date instanceof Date) || isNaN(date.getTime())) {
      return false
    }

    return date.getTime() > Date.now()
  } catch (error) {
    console.error('❌ isFuture - 解析异常:', error)
    return false
  }
}

export function isPast(dateTimeStr: string | Date | null | undefined): boolean {
  // ✅ 安全检查
  if (dateTimeStr === null || dateTimeStr === undefined || dateTimeStr === '') {
    return false
  }

  try {
    const date = typeof dateTimeStr === 'string' ? new Date(dateTimeStr) : dateTimeStr

    // ✅ 检查日期是否有效
    if (!(date instanceof Date) || isNaN(date.getTime())) {
      return false
    }

    return date.getTime() < Date.now()
  } catch (error) {
    console.error('❌ isPast - 解析异常:', error)
    return false
  }
}

export function getDaysDiff(date1: string | Date | null | undefined, date2: string | Date | null | undefined): number {
  // ✅ 安全检查
  if (!date1 || !date2) return 0

  try {
    const d1 = typeof date1 === 'string' ? new Date(date1) : date1
    const d2 = typeof date2 === 'string' ? new Date(date2) : date2

    // ✅ 检查日期是否有效
    if (!(d1 instanceof Date) || isNaN(d1.getTime()) ||
        !(d2 instanceof Date) || isNaN(d2.getTime())) {
      console.warn('⚠️ getDaysDiff - 无效日期')
      return 0
    }

    const diffTime = d2.getTime() - d1.getTime()
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24))
  } catch (error) {
    console.error('❌ getDaysDiff - 解析异常:', error)
    return 0
  }
}

export function addDays(dateTimeStr: string | Date, days: number): Date {
  try {
    const date = typeof dateTimeStr === 'string' ? new Date(dateTimeStr) : dateTimeStr

    // ✅ 检查日期是否有效
    if (!(date instanceof Date) || isNaN(date.getTime())) {
      console.warn('⚠️ addDays - 无效日期，返回当前日期')
      const result = new Date()
      result.setDate(result.getDate() + days)
      return result
    }

    const result = new Date(date)
    result.setDate(result.getDate() + days)
    return result
  } catch (error) {
    console.error('❌ addDays - 解析异常:', error)
    const result = new Date()
    result.setDate(result.getDate() + days)
    return result
  }
}

export function getWeekStart(date: Date = new Date()): Date {
  const d = new Date(date)
  const day = d.getDay()
  const diff = d.getDate() - day + (day === 0 ? -6 : 1)
  return new Date(d.setDate(diff))
}

export function getWeekEnd(date: Date = new Date()): Date {
  const weekStart = getWeekStart(date)
  return addDays(weekStart, 6)
}

/**
 * 将日期格式化为 API 所需的完整时间字符串 (yyyy-MM-ddTHH:mm:ss)
 * @param dateTimeStr 日期字符串或 Date 对象
 * @param isEndTime 是否为结束时间（如果是，则设置为 23:59:59）
 * @returns 格式化后的时间字符串
 */
export function formatForAPI(dateTimeStr: string | Date | null | undefined, isEndTime: boolean = false): string {
  // ✅ 安全检查：防止 undefined/null 导致 TypeError
  if (dateTimeStr === null || dateTimeStr === undefined || dateTimeStr === '') {
    console.warn('⚠️ formatForAPI - 收到空值:', dateTimeStr)
    return ''
  }

  try {
    const date = typeof dateTimeStr === 'string' ? new Date(dateTimeStr) : dateTimeStr

    // ✅ 检查日期是否有效
    if (!(date instanceof Date) || isNaN(date.getTime())) {
      console.warn('⚠️ formatForAPI - 无效日期:', dateTimeStr, '→ 解析结果:', date)
      return ''
    }

    const year = date.getFullYear()
    const month = padZero(date.getMonth() + 1)
    const day = padZero(date.getDate())

    if (isEndTime) {
      // 结束时间：当天的 23:59:59（使用 T 分隔符，符合 ISO 8601 标准）
      return `${year}-${month}-${day}T23:59:59`
    } else {
      // 开始时间：当天的 00:00:00（使用 T 分隔符，符合 ISO 8601 标准）
      return `${year}-${month}-${day}T00:00:00`
    }
  } catch (error) {
    console.error('❌ formatForAPI - 解析异常:', error, '输入值:', dateTimeStr)
    return ''
  }
}
/**
 * 将日期字符串转换为带时间的完整格式 (yyyy-MM-ddTHH:mm:ss)
 * 用于 API 参数传递
 */
export function toAPIDateTime(dateStr: string | null | undefined): { start: string; end: string } {
  // ✅ 安全检查
  if (!dateStr) {
    return { start: '', end: '' }
  }

  try {
    return {
      start: formatForAPI(dateStr, false),  // 2024-01-15T00:00:00
      end: formatForAPI(dateStr, true)     // 2024-01-15T23:59:59
    }
  } catch (error) {
    console.error('❌ toAPIDateTime - 解析异常:', error)
    return { start: '', end: '' }
  }
}

/**
 * 判断排期是否已过期（开始时间已过）
 * @param startAt - 排期开始时间字符串
 * @returns true = 已过期
 */
export function isScheduleExpired(startAt: string | null | undefined): boolean {
  if (!startAt) {
    console.warn('[isScheduleExpired] startAt 为空，默认不阻止')
    return false
  }
  try {
    return new Date(startAt).getTime() < Date.now()
  } catch {
    console.warn('[isScheduleExpired] 日期解析失败:', startAt)
    return false
  }
}

/**
 * 判断排期是否在可预约时间窗口内（默认两周）
 * @param startAt - 排期开始时间字符串
 * @param maxDays - 最大提前预约天数，默认 14 天
 * @returns true = 在窗口内
 */
export function isWithinBookingWindow(
  startAt: string | null | undefined,
  maxDays: number = 14
): boolean {
  if (!startAt) {
    console.warn('[isWithinBookingWindow] startAt 为空，默认允许')
    return true
  }
  try {
    const now = new Date()
    const maxDate = new Date(now)
    maxDate.setDate(now.getDate() + maxDays)
    maxDate.setHours(23, 59, 59, 999)
    return new Date(startAt).getTime() <= maxDate.getTime()
  } catch {
    console.warn('[isWithinBookingWindow] 日期解析失败:', startAt)
    return true
  }
}