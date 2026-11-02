/**
 * 图片地址解析（全管理端统一入口）。
 *
 * 业务表存 object_key（如 "t/1/banner/uuid.png"），私有 OSS Bucket 下必须换成
 * 预签名 URL 才能显示。后端各列表接口已尽量返回可直接访问的 URL，但首页配置
 * draft 返回的是原始 object_key（编辑态需保留 key），因此管理端预览需要：
 *
 * - 完整 URL：原样返回
 * - object_key / 历史 /uploads/ 绝对路径：调用 /upload/url/{key} 换预签名地址
 *
 * 预签名结果按 key 做内存缓存，避免重复请求；过期后由 resolveImageUrlAsync 重新获取。
 */
import { commonApi } from '@dance-saas/api-client'

const resolvedCache = new Map<string, string>()
const pendingRequests = new Map<string, Promise<string>>()

/** 兼容历史数据：把 /uploads/{key} 还原成 object_key */
function objectKeyOf(value: string): string {
  return value.replace(/^\/uploads\//, '')
}

function isRemoteUrl(value: string): boolean {
  return /^https?:\/\//.test(value)
}

/**
 * 同步读取已解析的预览地址（模板绑定用）。
 * 未解析出结果时返回空串，由 resolveImageUrlAsync 在数据变化时填充缓存。
 */
export function previewImageUrl(value?: string | null): string {
  if (!value) return ''
  if (isRemoteUrl(value)) return value
  return resolvedCache.get(objectKeyOf(value)) || ''
}

/**
 * 异步把 object_key 换成可访问 URL，并进行缓存。
 * 完整 URL 直接返回；失败时返回空串（前端显示占位图，不阻塞渲染）。
 */
export async function resolveImageUrlAsync(value?: string | null): Promise<string> {
  if (!value) return ''
  if (isRemoteUrl(value)) return value

  const key = objectKeyOf(value)
  const cached = resolvedCache.get(key)
  if (cached) return cached

  let pending = pendingRequests.get(key)
  if (!pending) {
    pending = commonApi
      .getObjectUrl(key)
      .then(res => {
        const url = res?.data?.url || ''
        if (url) resolvedCache.set(key, url)
        return url
      })
      .catch(() => '')
      .finally(() => pendingRequests.delete(key))
    pendingRequests.set(key, pending)
  }
  return pending
}

/** 批量预热缓存（去重、忽略空值） */
export async function warmImageUrls(values: Array<string | null | undefined>): Promise<void> {
  const keys = new Set(values.filter((v): v is string => !!v && !isRemoteUrl(v)))
  await Promise.all(Array.from(keys).map(v => resolveImageUrlAsync(v)))
}

/**
 * 历史同步解析（仅用于后端已解析 URL 的页面；不发起网络请求）。
 */
export function resolveImageUrl(value?: string | null): string {
  if (!value) return ''
  if (isRemoteUrl(value)) return value
  if (value.startsWith('/')) return value
  return `/uploads/${value}`
}
