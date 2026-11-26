/**
 * 实时推送事件 → 页面数据刷新桥接（admin-web）。
 *
 * 职责边界：
 *   - 只做「事件 type 分发」，不新建请求层；刷新动作由各页面注册的既有加载函数完成，
 *     加载函数内部仍走 @dance-saas/api-client。
 *   - 未知 type 直接忽略（契约外事件不得影响页面）。
 *   - 协议与重连由 utils/notify.ts 负责，本文件不感知连接状态。
 */
import { onChange, onReconnect } from './notify'

/** 需要刷新的数据通道 */
export type NotifyChannel = 'bookings' | 'schedules'

/** 事件 type → 数据通道；未知 type 不在表中，安全忽略 */
const EVENT_CHANNELS: Readonly<Record<string, readonly NotifyChannel[]>> = {
  'booking.created': ['bookings', 'schedules'],
  'booking.cancelled': ['bookings', 'schedules'],
  'booking.changed': ['bookings', 'schedules'],
  'schedule.cancelled': ['schedules', 'bookings'],
}

type RefreshHandler = () => void

const channelHandlers = new Map<NotifyChannel, Set<RefreshHandler>>()
let unsubscribe: (() => void) | null = null
let unsubscribeReconnect: (() => void) | null = null

/**
 * 页面注册「本页可见时需要执行的既有加载函数」，返回注销函数。
 * 页面卸载时必须调用注销函数，避免重复订阅与内存泄漏。
 */
export function registerNotifyRefresh(channel: NotifyChannel, handler: RefreshHandler): () => void {
  let set = channelHandlers.get(channel)
  if (!set) {
    set = new Set<RefreshHandler>()
    channelHandlers.set(channel, set)
  }
  set.add(handler)

  return () => {
    const current = channelHandlers.get(channel)
    if (!current) return
    current.delete(handler)
    if (current.size === 0) channelHandlers.delete(channel)
  }
}

function dispatch(channels: readonly NotifyChannel[]): void {
  for (const channel of channels) {
    const set = channelHandlers.get(channel)
    if (!set) continue
    // 复制一份，避免 handler 内部增删订阅影响本次分发
    for (const handler of Array.from(set)) {
      try {
        handler()
      } catch (err) {
        console.error('[notify] 数据刷新失败:', err)
      }
    }
  }
}

/** 应用启动时调用一次；重复调用无副作用（HMR / 重复挂载安全） */
export function startNotifySync(): void {
  if (unsubscribe) return
  unsubscribe = onChange(event => {
    const channels = EVENT_CHANNELS[event.type]
    if (!channels) return
    dispatch(channels)
  })
  // 重连补齐：断线期间可能错过信号，重连成功后刷新当前所有已注册通道
  unsubscribeReconnect = onReconnect(() => {
    dispatch(Array.from(channelHandlers.keys()))
  })
}

/** 应用卸载时取消事件订阅 */
export function stopNotifySync(): void {
  unsubscribe?.()
  unsubscribe = null
  unsubscribeReconnect?.()
  unsubscribeReconnect = null
}
