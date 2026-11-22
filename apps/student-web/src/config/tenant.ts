/**
 * 单实例多机构部署：机构标识由部署环境注入，登录/注册页不再要求用户手动输入。
 *
 * 换机构部署时通过构建期环境变量覆盖：
 *   VITE_TENANT_SLUG=your-org npm run build
 */
export const DEPLOY_TENANT_SLUG: string =
  (import.meta.env.VITE_TENANT_SLUG as string | undefined)?.trim() || 'dance-school'

/** 当前部署的机构标识（登录、注册均使用）。 */
export function getTenantSlug(): string {
  return DEPLOY_TENANT_SLUG
}
