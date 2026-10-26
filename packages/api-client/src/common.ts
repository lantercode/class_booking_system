import { apiClient } from './index'

export interface UploadImageResponse {
  object_key: string
  url: string
  mime: string
  size: number
  biz_type: string
}

export const commonApi = {
  /**
   * 上传图片
   * @param file - 图片文件
   * @param bizType - 业务场景：avatar | classroom_cover | banner | video_cover | notice
   */
  uploadImage(file: File, bizType: string = 'avatar'): Promise<{ code: number; msg: string; data: UploadImageResponse }> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('biz_type', bizType)

    return apiClient.post('/upload/image', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },
}
