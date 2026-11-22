/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 单实例部署的机构标识，登录时使用；换机构部署时覆盖 */
  readonly VITE_TENANT_SLUG?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
