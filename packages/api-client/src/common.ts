import { apiClient } from './index'

export interface UploadImageResponse {
  url: string
  filename: string
  size: number
  content_type: string
}

export const commonApi = {
  /**
   * 上传图片
   * @param file - 图片文件
   * @returns 上传结果，包含图片URL
   */
  uploadImage(file: File): Promise<{ code: number; msg: string; data: UploadImageResponse }> {
    const formData = new FormData()
    formData.append('file', file)
    
    return apiClient.post('/common/upload/image', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },
}
