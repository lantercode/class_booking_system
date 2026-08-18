/**
 * 统一导航工具
 * 使用 fade-in 动画替代默认的滑动动画，提升页面切换体验
 */

interface NavigateOptions {
  url: string
  animationType?: 'fade-in' | 'none' | 'slide-in-right' | 'slide-in-left' | 'slide-in-top' | 'slide-in-bottom'
  animationDuration?: number
  events?: any
  success?: (res: any) => void
  fail?: (err: any) => void
  complete?: () => void
}

export function navigateTo(options: NavigateOptions): void {
  uni.navigateTo({
    url: options.url,
    animationType: options.animationType || 'fade-in',
    animationDuration: options.animationDuration ?? 200,
    events: options.events,
    success: options.success,
    fail: options.fail,
    complete: options.complete
  })
}

export function redirectTo(options: NavigateOptions): void {
  uni.redirectTo({
    url: options.url,
    animationType: options.animationType || 'fade-in',
    animationDuration: options.animationDuration ?? 200,
    success: options.success,
    fail: options.fail,
    complete: options.complete
  })
}

export function navigateBack(delta: number = 1): void {
  uni.navigateBack({
    delta,
    animationType: 'fade-in',
    animationDuration: 200
  })
}