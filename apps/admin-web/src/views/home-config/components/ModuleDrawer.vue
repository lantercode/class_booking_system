<template>
  <el-drawer
    :model-value="visible"
    :title="`编辑 · ${moduleTypeLabel(module?.type || '')}`"
    size="560px"
    :close-on-click-modal="false"
    @update:model-value="(v: boolean) => !v && emit('close')"
  >
    <template v-if="module">
      <!-- Banner 编辑 -->
      <div v-if="module.type === 'banner'" class="module-form">
        <div class="banner-list">
          <div v-for="(item, idx) in bannerItems" :key="idx" class="banner-item">
            <div class="banner-item-header">
              <span class="banner-index">#{{ idx + 1 }}</span>
              <el-button type="danger" size="small" link @click="removeBannerItem(idx)"
                >删除</el-button
              >
            </div>
            <el-form :model="item" label-width="80px" size="default">
              <el-form-item label="图片" required>
                <el-upload
                  class="image-uploader"
                  :show-file-list="false"
                  :http-request="(opts: any) => handleImageUpload(opts, item, 'banner')"
                  :before-upload="beforeUpload"
                >
                  <img v-if="item.image_url" :src="imgSrc(item.image_url)" class="uploaded-image" />
                  <div v-else class="upload-placeholder">
                    <el-icon><Plus /></el-icon>
                    <span>上传 Banner 图片</span>
                  </div>
                </el-upload>
                <div class="upload-tip">支持 JPG/PNG/WEBP，最大 5MB</div>
              </el-form-item>
              <el-form-item label="标题" required>
                <el-input v-model="item.title" placeholder="Banner 标题" maxlength="30" />
              </el-form-item>
              <el-form-item label="副标题">
                <el-input v-model="item.subtitle" placeholder="副标题（选填）" maxlength="50" />
              </el-form-item>
              <el-form-item label="跳转链接">
                <el-input v-model="item.link_url" placeholder="点击后跳转的 URL（选填）" />
              </el-form-item>
            </el-form>
          </div>
          <el-button v-if="bannerItems.length < 5" class="add-btn" @click="addBannerItem">
            <el-icon><Plus /></el-icon>
            添加 Banner
          </el-button>
          <el-alert
            v-else
            title="最多支持 5 个 Banner"
            type="info"
            show-icon
            :closable="false"
            style="margin-top: 8px"
          />
        </div>
      </div>

      <!-- Teachers 编辑 -->
      <div v-else-if="module.type === 'teachers'" class="module-form">
        <el-form label-width="100px">
          <el-form-item label="选择教师" required>
            <el-select
              v-model="teacherConfig.teacher_ids"
              multiple
              filterable
              placeholder="从教师列表中选择"
              style="width: 100%"
              :loading="teacherLoading"
            >
              <el-option
                v-for="t in teacherOptions"
                :key="t.id"
                :label="`${t.nickname}`"
                :value="t.id"
              />
            </el-select>
          </el-form-item>
        </el-form>
      </div>

      <!-- Courses 编辑 -->
      <div v-else-if="module.type === 'courses'" class="module-form">
        <el-form label-width="100px">
          <el-form-item label="选择课程">
            <el-select
              v-model="courseConfig.course_ids"
              multiple
              filterable
              placeholder="选择要推荐的课程（选填，不选则按排序自动）"
              style="width: 100%"
              :loading="courseLoading"
            >
              <el-option v-for="c in courseOptions" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
          </el-form-item>
        </el-form>
      </div>

      <!-- Video 编辑（多视频项，参照 banner） -->
      <div v-else-if="module.type === 'video'" class="module-form">
        <div class="banner-list">
          <div v-for="(item, idx) in videoItems" :key="idx" class="banner-item">
            <div class="banner-item-header">
              <span class="banner-index">视频 #{{ idx + 1 }}</span>
              <el-button type="danger" size="small" link @click="removeVideoItem(idx)"
                >删除</el-button
              >
            </div>
            <el-form :model="item" label-width="80px" size="default">
              <el-form-item label="封面" required>
                <div class="cover-field">
                  <el-upload
                    class="cover-uploader"
                    :show-file-list="false"
                    :http-request="(opts: any) => handleVideoCoverUpload(opts, item)"
                    :before-upload="beforeUpload"
                  >
                    <img v-if="item.cover_url" :src="imgSrc(item.cover_url)" class="cover-image" />
                    <div v-else class="cover-placeholder">
                      <el-icon :size="22" color="#c0c4cc"><Plus /></el-icon>
                      <span>上传封面（16:9）</span>
                    </div>
                  </el-upload>
                </div>
                <div class="upload-tip">支持 JPG/PNG/WEBP，最大 5MB</div>
              </el-form-item>
              <el-form-item label="视频" required>
                <div class="video-field">
                  <el-upload
                    class="video-uploader"
                    :show-file-list="false"
                    :http-request="(opts: any) => handleVideoFileUpload(opts, item)"
                    :before-upload="beforeVideoUpload"
                  >
                    <div v-if="item.video_url" class="video-uploaded">
                      <el-icon :size="22" color="#409eff"><VideoPlay /></el-icon>
                      <span class="video-filename">已上传</span>
                    </div>
                    <div v-else class="video-placeholder">
                      <el-icon :size="22" color="#c0c4cc"><VideoPlay /></el-icon>
                      <span>上传视频文件</span>
                    </div>
                  </el-upload>
                </div>
                <el-input
                  v-model="item.video_url"
                  placeholder="或填外部视频 URL"
                  clearable
                  style="margin-top: 10px"
                />
                <div class="upload-tip">支持 MP4/WEBM/MOV，最大 200MB</div>
              </el-form-item>
              <el-form-item label="标题" required>
                <el-input v-model="item.title" placeholder="例如：本周舞蹈教学" maxlength="30" />
              </el-form-item>
              <el-form-item label="描述">
                <el-input
                  v-model="item.description"
                  type="textarea"
                  :rows="2"
                  placeholder="视频简介（选填）"
                  maxlength="100"
                />
              </el-form-item>
            </el-form>
          </div>
          <el-button v-if="videoItems.length < 10" class="add-btn" @click="addVideoItem">
            <el-icon><Plus /></el-icon>
            添加视频
          </el-button>
          <el-alert
            v-else
            title="最多支持 10 个视频"
            type="info"
            show-icon
            :closable="false"
            style="margin-top: 8px"
          />
        </div>
      </div>
    </template>

    <template #footer>
      <div class="drawer-footer">
        <el-button @click="emit('close')">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存草稿</el-button>
      </div>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, VideoPlay } from '@element-plus/icons-vue'
import type { UploadProps } from 'element-plus'
import {
  courseApi,
  userApi,
  type Course,
  type HomeConfigModule,
} from '@dance-saas/api-client'
import { previewImageUrl, resolveImageUrlAsync } from '@/utils/image'
import { uploadFileWithLoading, type UploadBizType } from '@/utils/upload'

const props = defineProps<{
  visible: boolean
  module: HomeConfigModule | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', module: HomeConfigModule): void
}>()

const saving = ref(false)
const teacherLoading = ref(false)
const courseLoading = ref(false)

// 各模块的临时编辑状态
const bannerItems = ref<any[]>([])
const videoItems = ref<any[]>([])
const teacherConfig = ref<{ teacher_ids: number[] }>({
  teacher_ids: [],
})
const courseConfig = ref<{ course_ids: number[] }>({
  course_ids: [],
})

// object_key → 预签名 URL 缓存（draft 存的是原始 key，私有 Bucket 需换签名才能预览）
const resolvedUrls = ref<Record<string, string>>({})

function imgSrc(value?: string | null): string {
  if (!value) return ''
  return resolvedUrls.value[value] || previewImageUrl(value)
}

async function hydrateImages() {
  const values: string[] = []
  bannerItems.value.forEach(it => {
    if (it.image_url) values.push(it.image_url)
  })
  videoItems.value.forEach(it => {
    if (it.cover_url) values.push(it.cover_url)
  })
  const unique = Array.from(new Set(values))
  if (unique.length === 0) return
  await Promise.all(
    unique.map(async v => {
      const url = await resolveImageUrlAsync(v)
      if (url) resolvedUrls.value[v] = url
    })
  )
  resolvedUrls.value = { ...resolvedUrls.value }
}

watch([bannerItems, videoItems], hydrateImages, { deep: true, immediate: true })

// 下拉选项
interface TeacherOption {
  id: number
  nickname: string
  title: string | null
}
const teacherOptions = ref<TeacherOption[]>([])
const courseOptions = ref<Course[]>([])

const TYPE_LABELS: Record<string, string> = {
  banner: 'Banner 轮播',
  teachers: '师资团队',
  courses: '推荐课程',
  video: '舞蹈视频',
}

function moduleTypeLabel(type: string) {
  return TYPE_LABELS[type] || type
}

// 监听 props.module 变化，同步到临时编辑状态
watch(
  () => props.module,
  m => {
    if (!m) return
    switch (m.type) {
      case 'banner':
        bannerItems.value = (m.items || []).map((it: any) => ({ ...it }))
        if (bannerItems.value.length === 0) addBannerItem()
        break
      case 'teachers': {
        const cfg = (m.config as any) || {}
        teacherConfig.value = {
          teacher_ids: cfg.teacher_ids || [],
        }
        break
      }
      case 'courses': {
        const cfg = (m.config as any) || {}
        courseConfig.value = {
          course_ids: cfg.course_ids || [],
        }
        break
      }
      case 'video': {
        videoItems.value = (m.items || []).map((it: any) => ({ ...it }))
        if (videoItems.value.length === 0) addVideoItem()
        break
      }
    }
  },
  { immediate: true }
)

// Banner 操作
function addBannerItem() {
  bannerItems.value.push({
    title: '',
    subtitle: '',
    image_url: '',
    link_url: '',
  })
}

function removeBannerItem(idx: number) {
  bannerItems.value.splice(idx, 1)
}

// Video 操作（多视频项，和 banner 同结构）
function addVideoItem() {
  videoItems.value.push({
    title: '',
    description: '',
    cover_url: '',
    video_url: '',
  })
}

function removeVideoItem(idx: number) {
  videoItems.value.splice(idx, 1)
}

// 图片上传
const beforeUpload: UploadProps['beforeUpload'] = file => {
  const allowed = ['image/jpeg', 'image/png', 'image/webp']
  if (!allowed.includes(file.type)) {
    ElMessage.error('仅支持 JPG/PNG/WEBP 格式')
    return false
  }
  if (file.size / 1024 / 1024 > 5) {
    ElMessage.error('图片不能超过 5MB')
    return false
  }
  return true
}

async function handleImageUpload(opts: any, item: any, bizType: UploadBizType) {
  const { file } = opts
  try {
    const res = await uploadFileWithLoading(file, bizType)
    item.image_url = res.data.object_key
    ElMessage.success('图片上传成功')
  } catch (e: any) {
    ElMessage.error(e?.msg || e?.response?.data?.msg || '上传失败')
  }
}

async function handleVideoCoverUpload(opts: any, item: any) {
  const { file } = opts
  try {
    const res = await uploadFileWithLoading(file, 'video_cover')
    item.cover_url = res.data.object_key
    ElMessage.success('封面上传成功')
  } catch (e: any) {
    ElMessage.error(e?.msg || e?.response?.data?.msg || '上传失败')
  }
}

const beforeVideoUpload: UploadProps['beforeUpload'] = file => {
  const allowed = ['video/mp4', 'video/webm', 'video/quicktime']
  if (!allowed.includes(file.type)) {
    ElMessage.error('仅支持 MP4 / WEBM / MOV 格式')
    return false
  }
  if (file.size / 1024 / 1024 > 200) {
    ElMessage.error('视频文件不能超过 200MB')
    return false
  }
  return true
}

async function handleVideoFileUpload(opts: any, item: any) {
  const { file } = opts
  try {
    const res = await uploadFileWithLoading(file, 'video')
    item.video_url = res.data.object_key
    ElMessage.success('视频上传成功，保存草稿后生效')
  } catch (e: any) {
    ElMessage.error(e?.msg || e?.response?.data?.msg || '视频上传失败')
  }
}

// 加载下拉选项
async function loadTeachers() {
  teacherLoading.value = true
  try {
    // 先用 role_code 过滤
    const res = await userApi.list({ page_size: 200, role_code: 'teacher' })
    let items = res.data.items

    // fallback：如果 role_code 过滤返回空，拉所有用户再前端过滤
    if (!items || items.length === 0) {
      const allRes = await userApi.list({ page_size: 500 })
      items = allRes.data.items.filter(
        (u: any) => Array.isArray(u.roles) && u.roles.includes('teacher')
      )
    }

    teacherOptions.value = items.map((u: any) => ({
      id: u.id,
      nickname: u.nickname || u.phone,
      title: null,
    }))
  } catch (e: any) {
    const msg = e?.response?.data?.msg || e?.msg || '加载教师列表失败'
    console.warn('[ModuleDrawer] loadTeachers failed', e)
    ElMessage.error(msg)
  } finally {
    teacherLoading.value = false
  }
}

async function loadCourses() {
  courseLoading.value = true
  try {
    const res = await courseApi.list({ page_size: 200 })
    courseOptions.value = res.data.items
  } catch (e) {
    console.warn('加载课程列表失败', e)
  } finally {
    courseLoading.value = false
  }
}

onMounted(() => {
  loadTeachers()
  loadCourses()
})

// 保存回传
function handleSave() {
  if (!props.module) return

  // === 必填校验 ===
  switch (props.module.type) {
    case 'banner': {
      if (bannerItems.value.length === 0) {
        ElMessage.warning('请至少添加 1 个 Banner')
        return
      }
      const withImg = bannerItems.value.filter(it => !it.image_url)
      if (withImg.length) {
        ElMessage.warning('每个 Banner 必须上传图片')
        return
      }
      const withoutTitle = bannerItems.value.filter(it => !it.title?.trim())
      if (withoutTitle.length) {
        ElMessage.warning('每个 Banner 必须填写标题')
        return
      }
      break
    }
    case 'teachers':
      if (!teacherConfig.value.teacher_ids || teacherConfig.value.teacher_ids.length === 0) {
        ElMessage.warning('请至少选择 1 位教师')
        return
      }
      break
    case 'courses':
      if (!courseConfig.value.course_ids || courseConfig.value.course_ids.length === 0) {
        ElMessage.warning('请至少选择 1 门课程')
        return
      }
      break
    case 'video': {
      if (videoItems.value.length === 0) {
        ElMessage.warning('请至少添加 1 个视频')
        return
      }
      const missingCover = videoItems.value.filter(it => !it.cover_url)
      if (missingCover.length) {
        ElMessage.warning('每个视频必须上传封面图')
        return
      }
      const missingTitle = videoItems.value.filter(it => !it.title?.trim())
      if (missingTitle.length) {
        ElMessage.warning('每个视频必须填写标题')
        return
      }
      const missingUrl = videoItems.value.filter(it => !it.video_url)
      if (missingUrl.length) {
        ElMessage.warning('每个视频必须上传或填写视频地址')
        return
      }
      break
    }
  }

  const result: HomeConfigModule = { ...props.module }

  switch (props.module.type) {
    case 'banner':
      result.items = bannerItems.value.filter(it => it.image_url && it.title?.trim())
      break
    case 'teachers':
      result.config = { teacher_ids: teacherConfig.value.teacher_ids }
      break
    case 'courses':
      result.config = { course_ids: courseConfig.value.course_ids }
      break
    case 'video':
      result.items = videoItems.value.filter(it => it.video_url && it.cover_url && it.title?.trim())
      break
  }

  emit('save', result)
}
</script>

<style lang="scss" scoped>
.module-form {
  padding: 8px 0;
}

.banner-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.banner-item {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 16px;
  background: #fafafa;
}

.banner-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.banner-index {
  font-weight: 600;
  color: #409eff;
}

.add-btn {
  width: 100%;
  border-style: dashed;
}

// Banner 图片上传（复用封面上传样式，尺寸略小适配 banner）
.image-uploader :deep(.el-upload) {
  border: 1px dashed #d9d9d9;
  border-radius: 8px;
  cursor: pointer;
  width: 280px;
  height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  transition: border-color 0.3s;

  &:hover {
    border-color: #409eff;
  }
}

.upload-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  color: #909399;
  font-size: 12px;
}

.uploaded-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

// 封面上传（视频模块封面）
.cover-field {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.cover-uploader {
  border: 1px dashed #d9d9d9;
  border-radius: 8px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: border-color 0.3s;
  width: 160px;
  height: 120px;

  &:hover {
    border-color: #409eff;
  }

  :deep(.el-upload) {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .cover-image {
    width: 100%;
    height: 100%;
    display: block;
    object-fit: cover;
  }

  .cover-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6px;
    color: #8c939d;
    font-size: 12px;
  }
}

// 视频上传
.video-field {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;

  .video-uploader {
    border: 1px dashed #d9d9d9;
    border-radius: 6px;
    cursor: pointer;
    overflow: hidden;
    transition: border-color 0.3s;
    width: 160px;
    height: 80px;
    flex-shrink: 0;

    &:hover {
      border-color: #409eff;
    }

    :deep(.el-upload) {
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
    }
  }

  .video-placeholder,
  .video-uploaded {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    font-size: 12px;
    color: #8c939d;
  }

  .video-uploaded {
    color: #409eff;
  }

  .video-filename {
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.upload-tip {
  display: block;
  width: 100%;
  font-size: 12px;
  color: #909399;
  margin-top: 6px;
  line-height: 1.5;
}

.uploaded-image.cover,
.upload-placeholder.cover {
  width: 160px;
  height: 90px;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
