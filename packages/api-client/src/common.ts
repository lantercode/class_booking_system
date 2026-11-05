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
      // 视频最大 200MB，且后端在 biz_type=video 时可能触发 ffmpeg 转码（最长 600s）；
      // 全局默认 15s 会直接中断上传，这里单独放宽到 15 分钟。
      timeout: 15 * 60 * 1000,
    })
  },

  /**
   * object_key → 可访问 URL（私有 OSS Bucket 下返回预签名地址）
   * 兼容历史数据里以 /uploads/ 开头的绝对路径
   */
  getObjectUrl(objectKey: string): Promise<{ code: number; msg: string; data: { url: string; expires_seconds?: number } }> {
    const key = objectKey.replace(/^\/uploads\//, '')
    return apiClient.get(`/upload/url/${key}`)
  },
}
