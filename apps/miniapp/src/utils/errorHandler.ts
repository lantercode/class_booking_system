export function handleError(error: any, message?: string) {
  console.error('[Error]', error)
  
  if (error?.errMsg?.includes('timeout')) {
    uni.showToast({ title: '请求超时，请重试', icon: 'none' })
    return
  }
  
  if (error?.errMsg?.includes('fail')) {
    uni.showToast({ title: '网络连接失败', icon: 'none' })
    return
  }
  
  if (error?.code === 401 || error?.message === '登录已过期') {
    return
  }
  
  if (error?.code === 403) {
    uni.showToast({ title: '权限不足', icon: 'none' })
    return
  }
  
  if (error?.code === 404) {
    uni.showToast({ title: '资源不存在', icon: 'none' })
    return
  }
  
  if (error?.code === 422) {
    if (error?.data?.errors) {
      const firstError = Object.values(error.data.errors)[0]
      uni.showToast({ title: firstError as string || '参数错误', icon: 'none' })
    }
    return
  }
  
  if (error?.msg) {
    uni.showToast({ title: error.msg, icon: 'none' })
    return
  }
  
  uni.showToast({ title: message || '操作失败', icon: 'none' })
}

export function handleNetworkError() {
  uni.showToast({ title: '网络请求失败', icon: 'none' })
}