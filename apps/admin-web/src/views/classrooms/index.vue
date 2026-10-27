<template>
  <div class="page-container">
    <div class="page-header">
      <h2>教室管理</h2>
      <el-button type="primary" @click="openCreateDialog"> 新增 </el-button>
    </div>

    <div style="display: flex; gap: 12px; margin-bottom: 16px; flex-shrink: 0">
      <el-input
        v-model="search"
        placeholder="搜索教室名称"
        style="width: 240px"
        clearable
        @input="onSearch"
      >
        <template #suffix>
          <el-icon class="search-icon" style="cursor: pointer" @click="onSearch">
            <Search />
          </el-icon>
        </template>
      </el-input>
    </div>

    <div v-if="loadError" class="list-error-block">
      <el-result icon="error" title="加载教室列表失败" :sub-title="loadError">
        <template #extra>
          <el-button type="primary" @click="fetchClassrooms">重试</el-button>
        </template>
      </el-result>
    </div>

    <div v-else v-loading="loading" class="classroom-content">
      <el-row :gutter="20" style="row-gap: 16px">
        <el-col v-for="room in classrooms" :key="room.id" :span="8">
          <el-card shadow="hover" class="classroom-card">
            <div class="card-body">
              <!-- 封面图 (左上) -->
              <div class="cover-wrapper">
                <img
                  v-if="room.cover_image_url"
                  :src="resolveCoverUrl(room.cover_image_url)"
                  class="cover-image"
                />
                <div v-else class="cover-placeholder">
                  <el-icon :size="28" color="#c0c4cc"><Picture /></el-icon>
                </div>
              </div>
              <!-- 右侧信息 -->
              <div class="info-wrapper">
                <div class="room-header">
                  <span class="room-name">{{ room.name }}</span>
                  <el-tag :type="room.status === 1 ? 'success' : 'warning'" size="small">
                    {{ room.status === 1 ? '正常' : '维护中' }}
                  </el-tag>
                </div>
                <div class="room-code" v-if="room.code">
                  <span class="code-label">编码</span>
                  <span class="code-value">{{ room.code }}</span>
                </div>
                <div class="room-location" v-if="room.location">
                  <el-icon><Location /></el-icon>
                  <span>{{ room.location }}</span>
                </div>
                <div class="room-info">
                  <div v-if="room.equipment?.length" class="info-item">
                    <el-icon><Setting /></el-icon>
                    <el-tooltip
                      :content="room.equipment.join('、')"
                      placement="top"
                      :disabled="room.equipment.join('、').length <= 15"
                    >
                      <span class="equipment-text">{{ room.equipment.join('、') }}</span>
                    </el-tooltip>
                  </div>
                  <div v-else class="info-item">
                    <el-icon><Setting /></el-icon>
                    <span style="color: #c0c4cc">--</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="room-actions">
              <el-button type="primary" size="small" link @click="openEditDialog(room)">
                编辑
              </el-button>
              <el-button
                :type="room.status === 1 ? 'warning' : 'success'"
                size="small"
                link
                @click="toggleStatus(room)"
              >
                {{ room.status === 1 ? '维护' : '启用' }}
              </el-button>
              <el-button type="danger" size="small" link @click="handleDelete(room)">
                删除
              </el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-empty v-if="!loading && classrooms.length === 0" description="暂无数据" />
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑教室' : '新增教室'"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="教室名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入教室名称" maxlength="50" />
        </el-form-item>
        <el-form-item label="教室编码">
          <el-input
            v-model="form.code"
            placeholder="留空自动生成 R-000 格式"
            maxlength="50"
            clearable
          />
        </el-form-item>
        <el-form-item label="位置">
          <el-input
            v-model="form.location"
            placeholder="如：A栋301"
            maxlength="200"
            clearable
          />
        </el-form-item>
        <el-form-item label="封面">
          <el-upload
            class="cover-uploader"
            :show-file-list="false"
            :before-upload="beforeCoverUpload"
            :http-request="handleCoverUpload"
          >
            <img
              v-if="coverPreviewUrl"
              :src="coverPreviewUrl"
              class="cover-uploader-img"
            />
            <div v-else class="cover-uploader-placeholder">
              <el-icon :size="24" color="#8c939d"><Plus /></el-icon>
              <span class="upload-tip">点击上传封面</span>
            </div>
          </el-upload>
          <div class="upload-hint">支持 JPG/PNG/WEBP，最大 5MB，建议 4:3 比例</div>
          <div
            v-if="form.cover_image_url"
            class="clear-cover"
            @click="clearCover"
          >
            <el-icon><Delete /></el-icon>
            <span>移除封面</span>
          </div>
        </el-form-item>
        <el-form-item label="设备">
          <el-select
            v-model="form.equipment"
            multiple
            filterable
            allow-create
            placeholder="请选择或输入设备"
            style="width: 100%"
            clearable
          >
            <el-option label="镜子" value="镜子" />
            <el-option label="把杆" value="把杆" />
            <el-option label="音响" value="音响" />
            <el-option label="投影仪" value="投影仪" />
            <el-option label="瑜伽垫" value="瑜伽垫" />
            <el-option label="灯光" value="灯光" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false"> 取消 </el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit"> 确定 </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import {
  type Classroom,
  classroomApi,
  type ClassroomCreateParams,
  type ClassroomUpdateParams,
  commonApi,
} from '@dance-saas/api-client'
import { Delete, Location, Picture, Plus, Search, Setting } from '@element-plus/icons-vue'
import type { UploadProps } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'

const loading = ref(false)
const loadError = ref('')
const submitting = ref(false)
const classrooms = ref<Classroom[]>([])
const search = ref('')

const dialogVisible = ref(false)
const isEdit = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref()

const form = ref<ClassroomCreateParams>({
  name: '',
  code: '',
  location: '',
  cover_image_url: '',
  equipment: [],
})

// 上传时临时保存的可访问 URL（用于预览）
const coverPreviewUrl = ref('')

const rules = {
  name: [{ required: true, message: '请输入教室名称', trigger: 'blur' }],
}

/** object_key / url 都能解析显示（业务表存 object_key，需拼本地存储前缀） */
function resolveCoverUrl(val: string | null | undefined): string {
  if (!val) return ''
  if (val.startsWith('http://') || val.startsWith('https://')) return val
  if (val.startsWith('/')) return val
  return `/uploads/${val}`
}

async function fetchClassrooms() {
  loading.value = true
  loadError.value = ''
  try {
    const res = await classroomApi.list({
      keyword: search.value || undefined,
      page_size: 100,
    })
    classrooms.value = res.data.items
  } catch (e: any) {
    loadError.value = e?.response?.data?.msg || '加载教室列表失败'
    ElMessage.error(loadError.value)
  } finally {
    loading.value = false
  }
}

function onSearch() {
  fetchClassrooms()
}

function openCreateDialog() {
  isEdit.value = false
  editingId.value = null
  form.value = { name: '', code: '', location: '', cover_image_url: '', equipment: [] }
  coverPreviewUrl.value = ''
  dialogVisible.value = true
  formRef.value?.clearValidate()
}

function openEditDialog(row: Classroom) {
  isEdit.value = true
  editingId.value = row.id
  form.value = {
    name: row.name,
    code: row.code || '',
    location: row.location || '',
    cover_image_url: row.cover_image_url || '',
    equipment: row.equipment || [],
  }
  coverPreviewUrl.value = resolveCoverUrl(row.cover_image_url)
  dialogVisible.value = true
  formRef.value?.clearValidate()
}

/** 封面上传前校验 */
const beforeCoverUpload: UploadProps['beforeUpload'] = file => {
  const allowedTypes = ['image/jpeg', 'image/png', 'image/webp']
  const isAllowed = allowedTypes.includes(file.type)
  const isLt5M = file.size / 1024 / 1024 < 5

  if (!isAllowed) {
    ElMessage.error('封面只能是 JPG/PNG/WEBP 格式')
    return false
  }
  if (!isLt5M) {
    ElMessage.error('封面大小不能超过 5MB')
    return false
  }
  return true
}

/** 封面上传 */
const handleCoverUpload = async (options: any) => {
  const { file } = options
  try {
    const result = await commonApi.uploadImage(file, 'classroom_cover')
    if (result.code === 0 || result.code === 200) {
      // 存 object_key 到后端字段
      form.value.cover_image_url = result.data.object_key
      // 用 url 做本地预览
      coverPreviewUrl.value = result.data.url
      ElMessage.success('封面上传成功')
    } else {
      ElMessage.error(result.msg || '封面上传失败')
    }
  } catch (e: any) {
    const msg = e?.response?.data?.msg || e?.message || '封面上传失败'
    ElMessage.error(msg)
  }
}

function clearCover() {
  form.value.cover_image_url = ''
  coverPreviewUrl.value = ''
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    // 构造 payload：空字符串转 undefined
    const payload: Record<string, any> = {
      name: form.value.name,
      equipment: form.value.equipment,
    }
    if (form.value.code?.trim()) payload.code = form.value.code.trim()
    else if (isEdit.value) payload.code = '' as any // edit 时清空可能有问题，保持原逻辑
    if (form.value.location?.trim()) payload.location = form.value.location.trim()
    if (form.value.cover_image_url?.trim()) payload.cover_image_url = form.value.cover_image_url.trim()
    else if (!isEdit.value) { /* create 允许空 */ }

    if (isEdit.value && editingId.value) {
      // update 走 patch，只传非空字段
      const updatePayload: Record<string, any> = {}
      if (payload.name !== undefined) updatePayload.name = payload.name
      if (form.value.code !== undefined) updatePayload.code = form.value.code || ''
      if (form.value.location !== undefined) updatePayload.location = form.value.location || ''
      if (form.value.cover_image_url !== undefined) updatePayload.cover_image_url = form.value.cover_image_url || ''
      if (form.value.equipment !== undefined) updatePayload.equipment = form.value.equipment

      await classroomApi.update(editingId.value, updatePayload as ClassroomUpdateParams)
      ElMessage.success('教室更新成功')
    } else {
      await classroomApi.create(payload as ClassroomCreateParams)
      ElMessage.success('教室创建成功')
    }
    dialogVisible.value = false
    fetchClassrooms()
  } catch (e: any) {
    const status = e?.response?.status
    if (status === 409) {
      ElMessage.error(e?.response?.data?.msg || '教室编码已存在，请修改')
    } else {
      ElMessage.error(e?.response?.data?.msg || '操作失败')
    }
  } finally {
    submitting.value = false
  }
}

async function toggleStatus(row: Classroom) {
  const newStatus = row.status === 1 ? 0 : 1
  const action = newStatus === 0 ? '维护' : '启用'
  try {
    await ElMessageBox.confirm(`确定要${action}教室「${row.name}」吗？`, '提示', {
      type: 'warning',
    })
    await classroomApi.update(row.id, { status: newStatus })
    ElMessage.success(`${action}成功`)
    fetchClassrooms()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.msg || '操作失败')
    }
  }
}

async function handleDelete(row: Classroom) {
  try {
    await ElMessageBox.confirm(`确定要删除教室「${row.name}」吗？此操作不可恢复。`, '警告', {
      type: 'error',
    })
    await classroomApi.remove(row.id)
    ElMessage.success('删除成功')
    fetchClassrooms()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.msg || '删除失败')
    }
  }
}

onMounted(() => {
  fetchClassrooms()
})
</script>

<style scoped lang="scss">
.search-icon:hover {
  color: #409eff;
}

.list-error-block {
  padding: 40px 0;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #ebeef5;
}

.classroom-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 4px;

  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: #dcdfe6;
    border-radius: 2px;
    transition: background 0.3s;
  }

  &::-webkit-scrollbar-thumb:hover {
    background: #c0c4cc;
  }
}

.classroom-card {
  margin-bottom: 16px;
  border-radius: 12px;
  height: 100%;

  :deep(.el-card__body) {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: 14px 16px;
  }

  .card-body {
    display: flex;
    gap: 12px;
    flex: 1;
    min-height: 0;
  }

  .cover-wrapper {
    flex-shrink: 0;
    width: 80px;
    height: 60px;
    border-radius: 8px;
    overflow: hidden;
    background: #f5f7fa;
    display: flex;
    align-items: center;
    justify-content: center;

    .cover-image {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }

    .cover-placeholder {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      height: 100%;
    }
  }

  .info-wrapper {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .room-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;

    .room-name {
      font-size: 16px;
      font-weight: 600;
      color: #1a1a2e;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .room-code {
    font-size: 12px;
    color: #909399;
    display: flex;
    align-items: center;
    gap: 6px;

    .code-label {
      background: #ecf5ff;
      color: #409eff;
      padding: 1px 6px;
      border-radius: 4px;
      font-size: 11px;
    }

    .code-value {
      font-family: 'Menlo', monospace;
    }
  }

  .room-location {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 13px;
    color: #606266;

    .el-icon {
      font-size: 14px;
      color: #909399;
    }
  }

  .room-info {
    margin-top: auto;

    .info-item {
      display: flex;
      align-items: center;
      gap: 6px;
      color: #606266;
      font-size: 12px;
      min-width: 0;

      .equipment-text {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }
  }

  .room-actions {
    display: flex;
    gap: 12px;
    padding-top: 8px;
    border-top: 1px solid #ebeef5;
    flex-shrink: 0;
    margin-top: 8px;

    .el-button {
      padding: 4px 0;
      font-size: 13px;
    }
  }
}

/* 上传组件 */
.cover-uploader {
  border: 1px dashed #d9d9d9;
  border-radius: 8px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  width: 160px;
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s;

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

.cover-uploader-img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

.cover-uploader-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  color: #8c939d;

  .upload-tip {
    font-size: 12px;
  }
}

.upload-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 6px;
}

.clear-cover {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
  font-size: 12px;
  color: #f56c6c;
  cursor: pointer;

  &:hover {
    text-decoration: underline;
  }
}
</style>
