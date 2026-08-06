import { createSSRApp } from 'vue'
// import { createPinia } from 'pinia'
import App from './App.vue'

export function createApp() {
  const app = createSSRApp(App)
  
  // 延迟创建 pinia，避免 getApp 报错
  // const pinia = createPinia()
  // app.use(pinia)
  
  return { app }
}