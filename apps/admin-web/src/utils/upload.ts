import { ElLoading } from 'element-plus'

import { commonApi } from '@dance-saas/api-client'

export type UploadBizType =
  | 'avatar'
  | 'course_cover'
  | 'classroom_cover'
  | 'banner'
  | 'video_cover'
  | 'notice'
  | 'video'

/**
 * 带全屏 loading 的文件上传（图片 / 视频）
 *
 * 大文件上传与后端转码耗时较长（视频最大 200MB，转码最长 600s），
 * 没有明确的过程反馈时用户会误以为页面卡死。
 */
export async function uploadFileWithLoading(
  file: File,
  bizType: UploadBizType,
  text?: string
): Promise<Awaited<ReturnType<typeof commonApi.uploadImage>>> {
  const isVideo = bizType === 'video'
  const loading = ElLoading.service({
    lock: true,
    text:
      text ??
      (isVideo ? '视频上传中，转码可能需要数分钟，请勿关闭页面…' : '图片上传中…'),
    background: 'rgba(0, 0, 0, 0.45)',
  })
  try {
    return await commonApi.uploadImage(file, bizType)
  } finally {
    loading.close()
  }
}
