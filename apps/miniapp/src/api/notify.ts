/**
 * 小程序实时推送（WebSocket）客户端。
 *
 * 后端契约：GET /api/v1/notify/ws?token=<access_token>&tenant_slug=<slug>
 *   - 小程序 WebSocket 无法自定义请求头，因此 token / tenant_slug 通过 query 传递
 *   - 完整地址由 VITE_API_BASE_URL 推导：http→ws、https→wss
 *   - 消息体与 Web 端 SSE 一致：{"type","entity_id","version"}
 *
 * 登录态来源与 api/index.ts 保持一致：
 *   - access_token：uni.getStorageSync("token")
 *   - 机构标识：resolveTenantSlug()（本地 tenant_slug > 部署配置 VITE_TENANT_SLUG）
 *
 * 说明：本文件只负责长连接协议适配与重连，不构成第三套 HTTP 请求层，
 *   常规请求仍必须走 src/api/index.ts。
 */
import { resolveTenantSlug } from "@/config/tenant";
import { BASE_URL } from "./index";

/** 推送事件（与后端固定契约一致） */
export interface NotifyEvent {
  type: string;
  entity_id: number;
  version: number;
}

export type NotifyHandler = (event: NotifyEvent) => void;

/** 登录态存储 key：与 api/index.ts、utils/auth.ts 保持一致 */
const TOKEN_STORAGE_KEY = "token";

/** 指数退避：1s → 2s → 4s … 上限 30s */
const RETRY_BASE_DELAY = 1000;
const RETRY_MAX_DELAY = 30_000;

const handlers = new Set<NotifyHandler>();
/** 连接重新建立后的回调（首次连接不触发），用于断线补齐 */
const reconnectHandlers = new Set<() => void>();

/** 是否处于「期望连接」状态（disconnect 后不再自动重连） */
let active = false;
/** 是否已经成功建立过连接（用于区分首次连接与重连） */
let hadConnected = false;
/** 连接代次：每次 connect/disconnect 自增，用于丢弃过期连接的回调与定时器 */
let generation = 0;
let retryCount = 0;
let retryTimer: ReturnType<typeof setTimeout> | null = null;
let socket: UniNamespace.SocketTask | null = null;
let appShowBound = false;

function readToken(): string {
  return String(uni.getStorageSync(TOKEN_STORAGE_KEY) || "").trim();
}

function clearRetryTimer(): void {
  if (retryTimer !== null) {
    clearTimeout(retryTimer);
    retryTimer = null;
  }
}

function emit(event: NotifyEvent): void {
  // 复制一份，避免 handler 内部增删订阅影响本次分发
  for (const handler of Array.from(handlers)) {
    try {
      handler(event);
    } catch (error) {
      console.error("[notify] 事件处理失败:", error);
    }
  }
}

function emitReconnect(): void {
  for (const handler of Array.from(reconnectHandlers)) {
    try {
      handler();
    } catch (error) {
      console.error("[notify] 重连补齐失败:", error);
    }
  }
}

/** 校验并归一化消息体，契约外的脏数据直接丢弃 */
function normalizeEvent(payload: unknown): NotifyEvent | null {
  if (!payload || typeof payload !== "object") return null;
  const raw = payload as Record<string, unknown>;
  const { type, entity_id: entityId, version } = raw;
  if (typeof type !== "string" || !type) return null;
  if (typeof entityId !== "number" || !Number.isFinite(entityId)) return null;
  if (typeof version !== "number" || !Number.isFinite(version)) return null;
  return { type, entity_id: entityId, version };
}

function handleMessage(data: string | ArrayBuffer): void {
  if (typeof data !== "string") return;

  let parsed: unknown;
  try {
    parsed = JSON.parse(data);
  } catch {
    return; // 非 JSON 消息忽略
  }

  const event = normalizeEvent(parsed);
  if (event) emit(event);
}

/** http(s) → ws(s)，并去掉末尾斜杠，避免拼出双斜杠 */
function toSocketBase(httpBase: string): string {
  const base = httpBase.replace(/\/+$/, "");
  if (base.startsWith("https://")) return `wss://${base.slice("https://".length)}`;
  if (base.startsWith("http://")) return `ws://${base.slice("http://".length)}`;
  return base; // 兜底：已经是 ws / wss
}

function buildSocketUrl(token: string, tenantSlug: string): string {
  const query = `token=${encodeURIComponent(token)}&tenant_slug=${encodeURIComponent(tenantSlug)}`;
  return `${toSocketBase(BASE_URL)}/notify/ws?${query}`;
}

function scheduleReconnect(gen: number): void {
  if (!active || gen !== generation) return;
  const delay = Math.min(RETRY_BASE_DELAY * 2 ** retryCount, RETRY_MAX_DELAY);
  retryCount += 1;
  clearRetryTimer();
  retryTimer = setTimeout(() => {
    retryTimer = null;
    openSocket(gen);
  }, delay);
}

function openSocket(gen: number): void {
  if (!active || gen !== generation) return;

  const token = readToken();
  if (!token) {
    // 未登录 / 被登出清空：不发起无意义连接，按退避等待 token 写回（如重新登录）
    scheduleReconnect(gen);
    return;
  }

  const url = buildSocketUrl(token, resolveTenantSlug());

  let task: UniNamespace.SocketTask;
  try {
    task = uni.connectSocket({
      url,
      // 显式传 complete：@dcloudio/types 对「无回调调用」会把返回值推断成 Promise，
      // 传入回调才能拿到 SocketTask 实例（仅类型层面，运行时同样返回 SocketTask）
      complete: () => undefined,
    });
  } catch (error) {
    console.error("[notify] 创建 WebSocket 连接失败:", error);
    scheduleReconnect(gen);
    return;
  }

  socket = task;

  task.onOpen(() => {
    if (gen !== generation || !active) return;
    // 连接成功，重置退避阶梯
    retryCount = 0;
    // 重连成功：通知上层做一次全量刷新，补齐断线期间错过的事件
    if (hadConnected) emitReconnect();
    hadConnected = true;
  });

  task.onMessage(res => {
    if (gen !== generation || !active) return;
    handleMessage(res.data as string | ArrayBuffer);
  });

  task.onClose(() => {
    if (socket === task) socket = null;
    if (gen !== generation || !active) return;
    scheduleReconnect(gen);
  });

  task.onError(() => {
    // onError 之后通常还会触发 onClose，重连统一交给 onClose，避免重复定时器
  });
}

/** 后台切回前台：若已断开且没有待执行的退避定时器，立即重连 */
function handleAppShow(): void {
  if (!active) return;
  if (socket || retryTimer !== null) return;
  retryCount = 0;
  openSocket(generation);
}

function bindAppShow(): void {
  if (appShowBound) return;
  appShowBound = true;
  uni.onAppShow(handleAppShow);
}

/** 订阅推送事件，返回取消订阅函数 */
export function onChange(handler: NotifyHandler): () => void {
  handlers.add(handler);
  return () => {
    handlers.delete(handler);
  };
}

/**
 * 订阅「连接重新建立」事件（首次连接不触发），返回取消订阅函数。
 * 用途：断线期间可能错过推送信号，重连后由上层主动刷新相关数据。
 */
export function onReconnect(handler: () => void): () => void {
  reconnectHandlers.add(handler);
  return () => {
    reconnectHandlers.delete(handler);
  };
}

/** 建立（并维持）推送连接；重复调用无副作用 */
export function connect(): void {
  if (active) return;
  active = true;
  retryCount = 0;
  hadConnected = false;
  bindAppShow();
  openSocket(++generation);
}

/** 主动断开并停止自动重连（登出、离开业务页时调用） */
export function disconnect(): void {
  active = false;
  hadConnected = false;
  generation += 1;
  retryCount = 0;
  clearRetryTimer();

  if (socket) {
    const task = socket;
    socket = null;
    try {
      task.close({ code: 1000, reason: "client disconnect" });
    } catch (error) {
      console.warn("[notify] 关闭 WebSocket 失败:", error);
    }
  }
}
