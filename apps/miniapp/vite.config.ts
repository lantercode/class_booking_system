import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

export default defineConfig({
  plugins: [uni()],
  build: {
    minify: process.env.NODE_ENV === 'production' ? 'terser' : false,
    target: 'es6', // 确保编译目标一致
    cssCodeSplit: false // 避免 CSS 代码分割问题
  },
  server: {
    port: 5173,
    open: false,
    watch: {
      usePolling: true,
      interval: 100
    }
  },
  // ✨ 全局 SCSS 配置（优雅方案：单一入口）
  css: {
    preprocessorOptions: {
      scss: {
        // ✅ 使用现代 Sass API（消除 legacy-js-api 警告）
        api: 'modern-compiler',

        // ✅ 直接引入统一的样式入口文件（符合项目架构）
        additionalData: `
          @use "sass:color";
          @import '@/styles/index.scss';
        `,

        // ✅ 静默所有废弃警告（包括 legacy-js-api）
        silenceDeprecations: [
          'legacy-js-api',           // 主要警告：旧版 JS API
          'import',                  // @import 弃用
          'global-builtin',          // 全局内置模块
          'color-functions'          // 颜色函数弃用（lighten/darken等）
        ]
      }
    },
    // 开发环境禁用 CSS sourcemap 提升构建速度
    devSourcemap: false
  }
})