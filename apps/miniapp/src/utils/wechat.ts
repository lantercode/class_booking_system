import { authApi, resetAuthState, clearAuthData } from '@/api'

export interface WxLoginResult {
  code: number
  msg?: string
  data?: {
    access_token: string
    refresh_token: string
    user: any
  }
}

export interface AutoLoginResult {
  success: boolean
  needBind?: boolean
  bindToken?: string
  decryptedPhone?: string
  errorMsg?: string
  role?: 'student' | 'teacher'
  isNewUser?: boolean
  user?: any
  token?: string
  msg?: string
}

/**
 * 微信自动登录（核心功能）
 * 调用 wx.login 获取 code，然后调用后端自动登录接口
 * 后端根据 openid 自动判断是否已绑定
 *
 * 返回:
 * - 已绑定: { success: true, token, user, ... }
 * - 未绑定: { success: true, needBind: true, bindToken: "xxx" }
 * - 失败:   { success: false, msg: "..." }
 */
export async function wechatAutoLogin(tenantSlug?: string): Promise<AutoLoginResult> {
  try {
    console.log('🔐 开始微信自动登录...')

    const loginRes = await new Promise<UniApp.LoginRes>((resolve, reject) => {
      uni.login({
        provider: 'weixin',
        success: (res) => resolve(res),
        fail: (err) => reject(err)
      })
    })

const result = await authApi.wxAutoLogin({
      code: loginRes.code,
      tenant_slug: tenantSlug || uni.getStorageSync('tenant_slug') || 'dance-school'
    })

    console.log('📡 后端返回:', JSON.stringify(result))

    const isValidCode = result.code === 0 || result.code === 200
    if (!isValidCode) {
      return { success: false, msg: result.msg || `登录失败(错误码: ${result.code})` }
    }

    const data = result.data as any
    if (!data) {
      return { success: false, msg: '服务器响应格式错误' }
    }

    if (data.need_bind) {
      console.log('📋 需要绑定手机号')
      return {
        success: true,
        needBind: true,
        bindToken: data.bind_token,
        msg: data.error_msg || '请绑定手机号完成登录'
      }
    }

    const access_token = data.access_token || data.token
    const refresh_token = data.refresh_token
    const user = data.user || {}

    if (!access_token) {
      return { success: false, msg: '服务器未返回访问令牌' }
    }

    resetAuthState()
    uni.setStorageSync('token', access_token)
    uni.setStorageSync('refresh_token', refresh_token || '')
    uni.setStorageSync('user_info', JSON.stringify(user))

    const role = user?.role || 'student'
    uni.setStorageSync('user_role', role)
    uni.setStorageSync('tenant_slug', tenantSlug || uni.getStorageSync('tenant_slug') || 'dance-school')

    console.log('🎉 登录成功！角色:', role)

    uni.$emit('login-success')

    return {
      success: true,
      role: role as 'student' | 'teacher',
      user,
      token: access_token
    }
  } catch (error: any) {
    console.error('❌ 微信自动登录异常:', error)
    return { success: false, msg: error.message || '网络异常，请重试' }
  }
}

/**
 * 微信手机号授权绑定
 * 用户点击 getPhoneNumber 按钮后，将加密数据发给后端解密并绑定
 */
export async function wechatBindPhone(
  bindToken: string,
  encryptedData: string,
  iv: string,
  tenantSlug?: string
): Promise<AutoLoginResult> {
  try {
    console.log('📱 开始手机号授权绑定...')

    const result = await authApi.wechatLogin({
      bind_token: bindToken,
      encrypted_data: encryptedData,
      iv: iv,
      tenant_slug: tenantSlug || uni.getStorageSync('tenant_slug') || 'dance-school'
    })

    console.log('📡 绑定返回:', JSON.stringify(result))

    const isValidCode = result.code === 0 || result.code === 200
    if (!isValidCode) {
      return { success: false, msg: result.msg || '绑定失败' }
    }

    const data = result.data as any

    if (data.need_bind) {
      console.log('⚠️ 手机号未注册:', data.decrypted_phone)
      return {
        success: true,
        needBind: true,
        bindToken: data.bind_token || bindToken,
        decryptedPhone: data.decrypted_phone,
        errorMsg: data.error_msg || '该手机号未注册'
      }
    }

    const access_token = data.access_token
    const refresh_token = data.refresh_token
    const user = data.user || {}

    if (!access_token) {
      return { success: false, msg: '服务器未返回访问令牌' }
    }

    resetAuthState()
    uni.setStorageSync('token', access_token)
    uni.setStorageSync('refresh_token', refresh_token || '')
    uni.setStorageSync('user_info', JSON.stringify(user))

    const role = user?.role || 'student'
    uni.setStorageSync('user_role', role)
    uni.setStorageSync('tenant_slug', tenantSlug || uni.getStorageSync('tenant_slug') || 'dance-school')

    console.log('🎉 绑定成功！角色:', role)
    console.log('✅ 已存储 tenant_slug:', uni.getStorageSync('tenant_slug'))

    uni.$emit('login-success')

    return {
      success: true,
      role: role as 'student' | 'teacher',
      user,
      token: access_token
    }
  } catch (error: any) {
    console.error('❌ 手机号绑定异常:', error)
    return { success: false, msg: error.message || '绑定失败，请重试' }
  }
}

/**
 * 手动输入手机号绑定（兜底方案）
 */
export async function wechatBindPhoneManual(
  bindToken: string,
  phone: string,
  tenantSlug?: string
): Promise<AutoLoginResult> {
  try {
    console.log('📱 手动输入手机号绑定:', phone)

 const result = await authApi.wechatLogin({
      bind_token: bindToken,
      phone: phone,
      tenant_slug: tenantSlug || uni.getStorageSync('tenant_slug') || 'dance-school'
    })

    console.log('📡 手动绑定返回:', JSON.stringify(result))

    const isValidCode = result.code === 0 || result.code === 200
    if (!isValidCode) {
      return { success: false, msg: result.msg || '绑定失败' }
    }

    const data = result.data as any

    if (data.need_bind) {
      return {
        success: false,
        msg: data.error_msg || '未找到该手机号的学员信息'
      }
    }

    const access_token = data.access_token
    const refresh_token = data.refresh_token
    const user = data.user || {}

    if (!access_token) {
      return { success: false, msg: '服务器未返回访问令牌' }
    }

    resetAuthState()
    uni.setStorageSync('token', access_token)
    uni.setStorageSync('refresh_token', refresh_token || '')
    uni.setStorageSync('user_info', JSON.stringify(user))

    const role = user?.role || 'student'
    uni.setStorageSync('user_role', role)
    uni.setStorageSync('tenant_slug', tenantSlug || uni.getStorageSync('tenant_slug') || 'dance-school')

    console.log('🎉 手动绑定成功！')

    uni.$emit('login-success')

    return {
      success: true,
      role: role as 'student' | 'teacher',
      user,
      token: access_token
    }
  } catch (error: any) {
    console.error('❌ 手动绑定异常:', error)
    return { success: false, msg: error.message || '绑定失败，请重试' }
  }
}

/**
 * 传统微信登录（保留兼容）
 */
export async function wxLogin(role: 'student' | 'teacher'): Promise<WxLoginResult> {
  return new Promise((resolve) => {
    uni.login({
      provider: 'weixin',
      success: async (loginRes) => {
        try {
          const authApiWithLegacyWxLogin = authApi as typeof authApi & {
            wxLogin?: (data: { code: string; role: 'student' | 'teacher' }) => Promise<any>
          }

          const result = await (authApiWithLegacyWxLogin.wxLogin?.({
            code: loginRes.code,
            role: role
          }) ?? authApiWithLegacyWxLogin.wxAutoLogin?.({
            code: loginRes.code,
            tenant_slug: uni.getStorageSync('tenant_slug') || 'dance-school'
          }))

          if (!result) {
            resolve({ code: -1, msg: '登录接口不可用' })
            return
          }

          if (result.code === 0 || result.code === 200) {
            resetAuthState()
            const { access_token, refresh_token, user } = result.data || {}
            uni.setStorageSync('token', access_token || '')
            uni.setStorageSync('refresh_token', refresh_token || '')
            uni.setStorageSync('user_info', JSON.stringify(user || {}))
            uni.setStorageSync('user_role', role)
            uni.$emit('login-success')
            resolve({ code: 0, data: result.data })
          } else {
            resolve({ code: -1, msg: result.msg || '登录失败' })
          }
        } catch (error) {
          console.error('微信登录失败', error)
          resolve({ code: -1, msg: '登录失败' })
        }
      },
      fail: (err) => {
        console.error('微信登录失败', err)
        resolve({ code: -1, msg: '微信授权失败' })
      }
    })
  })
}

/**
 * 获取用户信息（用于完善资料）
 */
export async function getUserInfo(): Promise<any> {
  return new Promise((resolve) => {
    uni.getUserProfile({
      desc: '用于完善会员资料',
      success: (res) => {
        resolve(res.userInfo)
      },
      fail: (err) => {
        console.error('获取用户信息失败', err)
        resolve(null)
      }
    })
  })
}

/**
 * 获取默认的机构标识
 */
export function getDefaultTenant(): string {
  return uni.getStorageSync('tenant_slug') || 'dance-school'
}

/**
 * 微信解绑
 * 解除当前用户与微信账号的绑定关系
 * 解绑成功后会自动清除本地登录态并跳转到登录页
 */
export async function wechatUnbind(): Promise<{ success: boolean; msg: string }> {
  try {
    const result = await authApi.wechatUnbind()
    if (result.code === 0 || result.code === 200) {
      try {
        await authApi.logout()
      } catch {
        // 后端注销失败不阻塞流程，本地状态仍然会清除
        console.warn('⚠️ 后端注销请求失败，已清除本地状态')
      }

      resetAuthState()

      uni.$emit('logout')

      return { success: true, msg: '微信已解绑' }
    }
    return { success: false, msg: result.msg || '解绑失败' }
  } catch (error: any) {
    console.error('❌ 微信解绑异常:', error)
    return { success: false, msg: error.message || '解绑失败，请重试' }
  }
}