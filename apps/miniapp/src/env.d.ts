/// <reference types="vite/client" />

declare module '*.vue' {
  import { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  /** 单实例部署的机构标识（小程序无机构输入入口，统一由此注入） */
  readonly VITE_TENANT_SLUG?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}