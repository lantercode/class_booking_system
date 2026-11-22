/**
 * 单实例多机构部署：机构标识由部署环境决定。
 *
 * 小程序没有「机构标识」输入入口，因此机构标识统一由构建期环境变量
 * VITE_TENANT_SLUG 注入，禁止在业务代码里散落硬编码的机构标识。
 */
export const DEPLOY_TENANT_SLUG: string =
  (import.meta.env.VITE_TENANT_SLUG as string | undefined)?.trim() || 'dance-school'

/**
 * 解析当前机构标识：显式传入 > 本地登录态 > 部署配置。
 */
export function resolveTenantSlug(explicit?: string): string {
  const slug = (explicit || uni.getStorageSync('tenant_slug') || '').trim()
  return slug || DEPLOY_TENANT_SLUG
}
