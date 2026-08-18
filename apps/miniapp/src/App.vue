<template>
  <!-- AI 助手在各页面独立引入，不在此处渲染 -->
</template>

<script setup lang="ts">
import { onLaunch, onShow, onHide } from '@dcloudio/uni-app'
import { validateToken, redirectToHome } from '@/utils/auth'

onLaunch(async () => {
  console.log('🚀 App Launch - 微信小程序启动')
  
  // 🔍 调试：打印所有关键本地存储数据
  printStorageDebugInfo()
  
  try {
    // 检查是否已有 Token
    const token = uni.getStorageSync('token')
    
    if (token) {
      console.log('✅ 检测到本地存储的 Token')
      
      // 验证 Token 是否有效
      const isValid = await validateToken()
      
      if (isValid) {
        console.log('🎉 Token 有效，准备跳转到主页...')
        
        // 延迟一帧确保页面渲染完成
        setTimeout(() => {
          redirectToHome()
        }, 100)
      } else {
        console.log('⚠️ Token 已失效或过期')
        // 不清除，让用户在授权页重新登录
      }
    } else {
      console.log('ℹ️ 未检测到 Token，显示授权页')
    }
    
  } catch (error) {
    console.error('❌ App 启动时验证 Token 失败:', error)
    // 出错时不做任何处理，默认显示授权页
  }
})

/**
 * 打印本地存储调试信息（开发环境专用）
 */
function printStorageDebugInfo() {
  const separator = '━'.repeat(50)
  
  console.log(`\n${separator}`)
  console.log('📦 本地存储数据概览 (Local Storage Debug)')
  console.log(`${separator}\n`)
  
  // 关键业务数据
  const keyMappings = [
    { key: 'token', label: '访问令牌', mask: true },
    { key: 'refresh_token', label: '刷新令牌', mask: true },
    { key: 'user_info', label: '用户信息', parseJson: true },
    { key: 'user_role', label: '用户角色' },
    { key: 'tenant_slug', label: '机构标识' },     // ← 你要看的这个！
  ]
  
  keyMappings.forEach(({ key, label, mask, parseJson }) => {
    const value = uni.getStorageSync(key)
    
    if (!value || value === '') {
      console.log(`❌ ${label} (${key}): [空/不存在]`)
    } else if (mask) {
      // 脱敏显示（只显示前8位和后4位）
      const strValue = String(value)
      console.log(
        `✅ ${label} (${key}): ${strValue.substring(0, 8)}...${strValue.substring(strValue.length - 4)} ` +
        `(长度: ${strValue.length})`
      )
    } else if (parseJson) {
      // JSON 格式化输出
      try {
        const parsed = JSON.parse(value)
        console.log(`✅ ${label} (${key}):`, parsed)
      } catch {
        console.log(`✅ ${label} (${key}):`, value)
      }
    } else {
      console.log(`✅ ${label} (${key}):`, value)
    }
  })
  
  console.log(`\n${separator}`)
  
  // 存储统计信息
  const storageInfo = uni.getStorageInfoSync()
  console.log(`💾 存储统计:`)
  console.log(`   • keys 数量: ${storageInfo.keys.length}`)
  console.log(`   • 当前大小: ${(storageInfo.currentSize / 1024).toFixed(2)} KB`)
  console.log(`   • 限制大小: ${storageInfo.limitSize} MB`)
  console.log(`   • 所有 keys:`, storageInfo.keys)
  console.log(`${separator}\n`)
}

onShow(() => {
  console.log('📱 App Show - 小程序前台运行')
})

onHide(() => {
  console.log('📴 App Hide - 小程序后台运行')
})
</script>

<style lang="scss">
/* ✅ 显式导入 Design System 变量（确保根组件可用） */

page {
  background-color: $background-primary;
  font-family: $font-family-base;
  font-size: $font-size-body;
  color: $text-primary;
  line-height: $line-height-normal;
  -webkit-font-smoothing: antialiased;
}

/* 全局容器 */
.container {
  padding: $space-lg;
}

/* 卡片系统 - 高级轻奢风格 */
.card {
  background: $card-background;       // 更新：使用正确的变量名（纯白背景）
  border-radius: $radius-lg;
  padding: $space-lg;
  margin-bottom: $space-md;
  box-shadow: $shadow-sm;             // 使用新的柔和阴影
}

/* 文字颜色工具类 */
.text-primary {
  color: $primary-solid;
}

.text-secondary {
  color: $text-secondary;
}

.text-muted {
  color: $text-muted;
}

.text-success {
  color: $color-success;
}

.text-warning {
  color: $color-warning;
}

.text-danger {
  color: $color-danger;
}

/* 字体大小工具类 */
.text-xs { font-size: $font-size-tiny; }
.text-sm { font-size: $font-size-caption; }
.text-base { font-size: $font-size-body; }
.text-lg { font-size: $font-size-body-lg; }
.text-xl { font-size: $font-size-h4; }
.text-2xl { font-size: $font-size-h3; }

/* Flexbox 工具类 */
.flex { display: flex; }
.flex-col { flex-direction: column; }
.flex-row { flex-direction: row; }
.flex-wrap { flex-wrap: wrap; }

.items-center { align-items: center; }
.items-start { align-items: flex-start; }
.items-end { align-items: flex-end; }

.justify-center { justify-content: center; }
.justify-between { justify-content: space-between; }
.justify-around { justify-content: space-around; }
.justify-end { justify-content: flex-end; }

.flex-1 { flex: 1; }
.flex-shrink-0 { flex-shrink: 0; }

/* 注意：微信小程序不支持通用选择器 *，gap 工具类需手动设置 margin */

.mt-xs { margin-top: $space-xs; }
.mt-sm { margin-top: $space-sm; }
.mt-md { margin-top: $space-md; }
.mt-lg { margin-top: $space-lg; }
.mt-xl { margin-top: $space-xl; }

.mb-xs { margin-bottom: $space-xs; }
.mb-sm { margin-bottom: $space-sm; }
.mb-md { margin-bottom: $space-md; }
.mb-lg { margin-bottom: $space-lg; }
.mb-xl { margin-bottom: $space-xl; }

.p-xs { padding: $space-xs; }
.p-sm { padding: $space-sm; }
.p-md { padding: $space-md; }
.p-lg { padding: $space-lg; }
.p-xl { padding: $space-xl; }

/* 文本对齐 */
.text-left { text-align: left; }
.text-center { text-align: center; }
.text-right { text-align: right; }

/* 文本截断 */
.truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 圆角工具类 */
.rounded-none { border-radius: 0; }
.rounded-sm { border-radius: $radius-xs; }
.rounded { border-radius: $radius-md; }
.rounded-lg { border-radius: $radius-lg; }
.rounded-xl { border-radius: $radius-xl; }
.rounded-full { border-radius: $radius-full; }

/* 阴影工具类 */
.shadow-none { box-shadow: none; }
.shadow-sm { box-shadow: $shadow-sm; }
.shadow { box-shadow: $shadow-md; }
.shadow-lg { box-shadow: $shadow-lg; }
.shadow-xl { box-shadow: $shadow-xl; }

/* 溢出处理 */
.overflow-hidden { overflow: hidden; }
.overflow-auto { overflow: auto; }
.overflow-scroll { overflow: scroll; }

/* 宽度高度 */
.w-full { width: 100%; }
.h-full { height: 100%; }
.min-h-screen { min-height: 100vh; }

/* 光标样式 */
.cursor-pointer { cursor: pointer; }

/* 过渡动画 */
.transition-all {
  transition-property: all;
  transition-timing-function: ease;
  transition-duration: 300ms;
}
</style>