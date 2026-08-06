export interface ApiResponse<T = any> {
  code: number
  data: T
  msg: string
}

export interface PaginatedData<T = any> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export function extractData<T = any>(
  response: ApiResponse<T> | any,
  fallback: T = [] as unknown as T
): T {
  if (!response) return fallback
  
  const data = response.data
  
  if (data === null || data === undefined) {
    return fallback
  }
  
  return data
}

export function extractList<T = any>(
  response: ApiResponse<PaginatedData<T>> | ApiResponse<T[]> | any,
  fallback: T[] = []
): T[] {
  if (!response) {
    console.warn('extractList: response 为空')
    return fallback
  }
  
  const data = response.data
  
  if (data === null || data === undefined) {
    console.warn('extractList: response.data 为空', response)
    return fallback
  }
  
  // 情况 1: data 直接是数组
  if (Array.isArray(data)) {
    console.log('extractList: data 是数组，长度:', data.length)
    return data as T[]
  }
  
  // 情况 2: data 是对象，包含 items 属性（分页结构）
  if (typeof data === 'object' && 'items' in data && Array.isArray(data.items)) {
    console.log('extractList: data.items 是数组，长度:', data.items.length)
    return data.items as T[]
  }
  
  // 情况 3: data 是对象，包含 list 属性（某些 API 格式）
  if (typeof data === 'object' && 'list' in data && Array.isArray(data.list)) {
    console.log('extractList: data.list 是数组，长度:', data.list.length)
    return data.list as T[]
  }
  
  // 情况 4: data 是对象，包含 data 属性（嵌套结构）
  if (typeof data === 'object' && 'data' in data && Array.isArray(data.data)) {
    console.log('extractList: data.data 是数组，长度:', data.data.length)
    return data.data as T[]
  }
  
  // 情况 5: 尝试查找任何数组属性
  if (typeof data === 'object') {
    const arrayKeys = Object.keys(data).filter(key => Array.isArray(data[key]))
    if (arrayKeys.length > 0) {
      console.log(`extractList: 找到数组属性 ${arrayKeys[0]}，长度:`, data[arrayKeys[0]].length)
      return data[arrayKeys[0]] as T[]
    }
  }
  
  console.warn('extractList: 无法识别的数据格式:', typeof data, data)
  console.warn('response 完整结构:', JSON.stringify(response, null, 2))
  return fallback
}

export function extractSingle<T = any>(
  response: ApiResponse<T> | any,
  fallback: T | null = null
): T | null {
  if (!response) return fallback
  
  const data = response.data
  
  if (data === null || data === undefined) {
    return fallback
  }
  
  return data as T
}

export function isSuccess(response: ApiResponse | any): boolean {
  return response && (response.code === 0 || response.code === 200)
}

export function getErrorMessage(response: ApiResponse | any, defaultMsg: string = '操作失败'): string {
  if (!response) return defaultMsg
  
  return response.msg || defaultMsg
}