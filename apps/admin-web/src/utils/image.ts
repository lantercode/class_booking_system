/**
 * 图片地址解析（全管理端统一入口）。
 *
 * 业务表存 object_key（如 "t/1/avatar/uuid.png"），后端出参已尽量解析为可访问 URL；
 * 本函数作为历史数据的兜底：
 * - 完整 URL / 以 "/" 开头的绝对路径：原样返回
 * - object_key：拼本地静态前缀 /uploads/
 */
export function resolveImageUrl(value?: string | null): string {
  if (!value) return ''
  if (value.startsWith('http://') || value.startsWith('https://')) return value
  if (value.startsWith('/')) return value
  return `/uploads/${value}`
}
