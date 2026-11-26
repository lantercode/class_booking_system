/**
 * 管理端实时推送（SSE）客户端。
 *
 * 后端契约：GET /api/v1/notify/stream
 *   - 请求头：Authorization: Bearer <access_token>、x-tenant-slug: <slug>
 *   - 响应：text/event-stream，事件体为 data: {"type","entity_id","version"}
 *   - 心跳为注释行 ": ping"
 *
 * 为什么不用 EventSource：
 *   契约要求自定义 Authorization / x-tenant-slug 请求头，而 EventSource 不支持自定义请求头，
 *   因此这里用 fetch + response.body.getReader() 自行按空行分帧解析。
 *
 * 为什么不在这里刷新 token：
 *   项目统一的 401 刷新重放逻辑只存在于 packages/api-client 的 axios 拦截器里
 *   （见 architecture/contracts.md、frontend/vue.md），SSE 走 fetch 不经过该拦截器。
 *   此处再实现一套刷新会与统一逻辑重复并产生并发刷新竞态，所以遇到 401 只断开连接、
 *   按退避重连；等业务请求触发拦截器完成刷新后，下一次重连会从 localStorage 读到新 token。
 *
 * 说明：本文件只是流式读取的协议适配层，不构成第三套 HTTP 请求层，
 *   常规请求仍必须走 @dance-saas/api-client。
 */
import { getTenantSlug } from '@/config/tenant'

/** 推送事件（与后端固定契约一致） */
export interface NotifyEvent {
  type: string
  entity_id: number
  version: number
}

export type NotifyHandler = (event: NotifyEvent) => void

/** SSE 端点：同源相对路径，禁止硬编码绝对 URL */
const STREAM_URL = '/api/v1/notify/stream'

/** 登录态存储 key：与 packages/api-client 拦截器、stores/auth.ts 保持一致 */
const TOKEN_STORAGE_KEY = 'token'
const TENANT_STORAGE_KEY = 'tenantSlug'

/** 指数退避：1s → 2s → 4s … 上限 30s */
const RETRY_BASE_DELAY = 1000
const RETRY_MAX_DELAY = 30_000

/** 空闲超时：后端心跳 25s，超过 90s 未收到任何字节视为死连接并触发重连 */
const STREAM_IDLE_TIMEOUT = 90_000

const handlers = new Set<NotifyHandler>()
/** 连接重新建立后的回调（首次连接不触发），用于断线补齐 */
const reconnectHandlers = new Set<() => void>()

/** 是否处于「期望连接」状态（disconnect 后不再自动重连） */
let active = false
/** 是否已经成功建立过连接（用于区分首次连接与重连） */
let hadConnected = false
/** 连接代次：每次 connect/disconnect 自增，用于丢弃过期连接的回调与定时器 */
let generation = 0
let retryCount = 0
let retryTimer: ReturnType<typeof setTimeout> | null = null
let controller: AbortController | null = null
let onlineBound = false

function readAccessToken(): string {
  return (localStorage.getItem(TOKEN_STORAGE_KEY) || '').trim()
}

function readTenantSlug(): string {
  const stored = (localStorage.getItem(TENANT_STORAGE_KEY) || '').trim()
  return stored || getTenantSlug()
}

function clearRetryTimer(): void {
  if (retryTimer !== null) {
    clearTimeout(retryTimer)
    retryTimer = null
  }
}

function emit(event: NotifyEvent): void {
  // 复制一份，避免 handler 内部增删订阅影响本次分发
  for (const handler of Array.from(handlers)) {
    try {
      handler(event)
    } catch (err) {
      console.error('[notify] 事件处理失败:', err)
    }
  }
}

function emitReconnect(): void {
  for (const handler of Array.from(reconnectHandlers)) {
    try {
      handler()
    } catch (err) {
      console.error('[notify] 重连补齐失败:', err)
    }
  }
}

/** 校验并归一化事件体，契约外的脏数据直接丢弃，不向业务层抛出 */
function normalizeEvent(payload: unknown): NotifyEvent | null {
  if (!payload || typeof payload !== 'object') return null
  const raw = payload as Record<string, unknown>
  const { type, entity_id: entityId, version } = raw
  if (typeof type !== 'string' || !type) return null
  if (typeof entityId !== 'number' || !Number.isFinite(entityId)) return null
  if (typeof version !== 'number' || !Number.isFinite(version)) return null
  return { type, entity_id: entityId, version }
}

/** 解析单个 SSE 帧（已去掉帧尾空行），只关心 data 字段 */
function handleFrame(frame: string): void {
  const dataLines: string[] = []

  for (const rawLine of frame.split(/\r?\n/)) {
    if (!rawLine || rawLine.startsWith(':')) continue // 空行 / 心跳注释 ": ping"
    const colonIndex = rawLine.indexOf(':')
    const field = colonIndex === -1 ? rawLine : rawLine.slice(0, colonIndex)
    let value = colonIndex === -1 ? '' : rawLine.slice(colonIndex + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'data') dataLines.push(value)
  }

  if (dataLines.length === 0) return

  let parsed: unknown
  try {
    parsed = JSON.parse(dataLines.join('\n'))
  } catch {
    return // 非 JSON 帧（例如后端调试文本）忽略
  }

  const event = normalizeEvent(parsed)
  if (event) emit(event)
}

/** 从缓冲区中切出所有完整帧，返回剩余未完整数据 */
function drainFrames(buffer: string): string {
  let rest = buffer
  for (;;) {
    const match = /\r?\n\r?\n/.exec(rest)
    if (!match) break
    const frame = rest.slice(0, match.index)
    rest = rest.slice(match.index + match[0].length)
    handleFrame(frame)
  }
  return rest
}

/** 读取流并按 \n\n 分帧；流被服务端关闭或连接中断时返回 */
async function readStream(
  body: ReadableStream<Uint8Array>,
  gen: number,
  abort: AbortController
): Promise<void> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let idleTimer: ReturnType<typeof setTimeout> | null = null

  // 代理可能在上游断开后不关闭下游连接，靠空闲计时主动放弃死连接
  const armIdle = () => {
    if (idleTimer) clearTimeout(idleTimer)
    idleTimer = setTimeout(() => abort.abort(), STREAM_IDLE_TIMEOUT)
  }

  try {
    armIdle()
    for (;;) {
      const { done, value } = await reader.read()
      if (gen !== generation || !active) break
      if (done) break
      armIdle()
      buffer = drainFrames(buffer + decoder.decode(value, { stream: true }))
    }
    // 流结束：flush 解码器，尽量不丢掉最后一帧
    if (gen === generation && active) drainFrames(buffer + decoder.decode())
  } finally {
    if (idleTimer) clearTimeout(idleTimer)
    try {
      reader.releaseLock()
    } catch {
      // 已被 abort 时 releaseLock 可能抛错，忽略
    }
  }
}

function scheduleRetry(gen: number): void {
  if (!active || gen !== generation) return
  const delay = Math.min(RETRY_BASE_DELAY * 2 ** retryCount, RETRY_MAX_DELAY)
  retryCount += 1
  clearRetryTimer()
  retryTimer = setTimeout(() => {
    retryTimer = null
    void openStream(gen)
  }, delay)
}

async function openStream(gen: number): Promise<void> {
  if (!active || gen !== generation) return

  const token = readAccessToken()
  if (!token) {
    // 未登录 / 已登出：不发无意义请求，继续按退避等待（登录写回 token 后即可连上）
    scheduleRetry(gen)
    return
  }

  const abort = new AbortController()
  controller = abort

  try {
    const response = await fetch(STREAM_URL, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
        'x-tenant-slug': readTenantSlug(),
        Accept: 'text/event-stream',
      },
      cache: 'no-store',
      signal: abort.signal,
    })

    if (gen !== generation || !active) return

    if (response.status === 401) {
      // 见文件头注释：SSE 不经过 axios 拦截器，这里不自行刷新 token，退出后按退避重连
      void response.body?.cancel().catch(() => undefined)
      scheduleRetry(gen)
      return
    }

    if (!response.ok || !response.body) {
      void response.body?.cancel().catch(() => undefined)
      scheduleRetry(gen)
      return
    }

    // 连接已建立，重置退避阶梯
    retryCount = 0
    // 重连成功：通知上层做一次全量刷新，补齐断线期间错过的事件
    if (hadConnected) emitReconnect()
    hadConnected = true
    await readStream(response.body, gen, abort)

    // 服务端正常关闭流（如发布重启）也继续重连
    scheduleRetry(gen)
  } catch {
    // 主动 disconnect 触发的 abort 由代次判断过滤；其余网络错误走退避
    if (!active || gen !== generation) return
    scheduleRetry(gen)
  } finally {
    if (controller === abort) controller = null
  }
}

/** 网络恢复时跳过剩余退避，立即重连 */
function handleOnline(): void {
  if (!active) return
  if (!retryTimer && controller) return // 已有活跃连接，无需处理
  clearRetryTimer()
  retryCount = 0
  void openStream(generation)
}

function bindOnline(): void {
  if (onlineBound || typeof window === 'undefined') return
  window.addEventListener('online', handleOnline)
  onlineBound = true
}

function unbindOnline(): void {
  if (!onlineBound || typeof window === 'undefined') return
  window.removeEventListener('online', handleOnline)
  onlineBound = false
}

/** 订阅推送事件，返回取消订阅函数 */
export function onChange(handler: NotifyHandler): () => void {
  handlers.add(handler)
  return () => {
    handlers.delete(handler)
  }
}

/**
 * 订阅「连接重新建立」事件（首次连接不触发），返回取消订阅函数。
 * 用途：断线期间可能错过推送信号，重连后由上层主动刷新相关数据。
 */
export function onReconnect(handler: () => void): () => void {
  reconnectHandlers.add(handler)
  return () => {
    reconnectHandlers.delete(handler)
  }
}

/** 建立（并维持）推送连接；重复调用无副作用 */
export function connect(): void {
  if (active) return
  active = true
  retryCount = 0
  hadConnected = false
  bindOnline()
  void openStream(++generation)
}

/** 主动断开并停止自动重连（登出、离开管理端时调用） */
export function disconnect(): void {
  active = false
  hadConnected = false
  generation += 1
  retryCount = 0
  clearRetryTimer()
  unbindOnline()
  if (controller) {
    controller.abort()
    controller = null
  }
}
