<template>
  <div class="page-container">
    <div class="page-header">
      <h2>教室管理</h2>
      <el-button type="primary" @click="openCreateDialog">
        <el-icon><Plus /></el-icon>新增教室
      </el-button>
    </div>

    <div style="display:flex;gap:12px;margin-bottom:16px">
      <el-input v-model="search" placeholder="搜索教室名称" style="width:240px" clearable @input="onSearch" />
    </div>

    <el-row :gutter="20" v-loading="loading" style="row-gap:16px">
      <el-col v-for="room in classrooms" :key="room.id" :span="8">
        <el-card shadow="hover" class="classroom-card">
          <div class="room-header">
            <span class="room-name">{{ room.name }}</span>
            <el-tag :type="room.status === 1 ? 'success' : 'warning'" size="small">
              {{ room.status === 1 ? '正常' : '维护中' }}
            </el-tag>
          </div>
          <div class="room-info">
            <div class="info-item">
              <el-icon><User /></el-icon>
              <span>容纳 {{ room.capacity }} 人</span>
            </div>
            <div class="info-item" v-if="room.equipment?.length">
              <el-icon><Setting /></el-icon>
              <el-tooltip :content="room.equipment.join('、')" placement="top" :disabled="room.equipment.join('、').length <= 15">
                <span class="equipment-text">{{ room.equipment.join('、') }}</span>
              </el-tooltip>
            </div>
            <div class="info-item" v-else>
              <el-icon><Setting /></el-icon>
              <span style="color:#c0c4cc">暂无设备</span>
            </div>
          </div>
          <div class="room-actions">
            <el-button type="primary" size="small" @click="openEditDialog(room)">编辑</el-button>
            <el-button
              :type="room.status === 1 ? 'warning' : 'success'"
              size="small"
              @click="toggleStatus(room)"
            >{{ room.status === 1 ? '维护' : '启用' }}</el-button>
            <el-button type="danger" size="small" @click="handleDelete(room)">删除</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-empty v-if="!loading && classrooms.length === 0" description="暂无教室" />

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑教室' : '新增教室'"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="教室名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入教室名称" />
        </el-form-item>
        <el-form-item label="容量" prop="capacity">
          <el-input-number v-model="form.capacity" :min="1" :max="200" style="width:100%" />
        </el-form-item>
        <el-form-item label="设备">
          <el-select
            v-model="form.equipment"
            multiple
            filterable
            allow-create
            placeholder="请选择或输入设备"
            style="width:100%"
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
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Plus, User, Setting } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { classroomApi, type Classroom, type ClassroomCreateParams, type ClassroomUpdateParams } from '@dance-saas/api-client'

const loading = ref(false)
const submitting = ref(false)
const classrooms = ref<Classroom[]>([])
const search = ref('')

const dialogVisible = ref(false)
const isEdit = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref()

const form = ref<ClassroomCreateParams>({
  name: '',
  capacity: 20,
  equipment: [],
})

const rules = {
  name: [{ required: true, message: '请输入教室名称', trigger: 'blur' }],
  capacity: [{ required: true, message: '请输入容量', trigger: 'blur' }],
}

async function fetchClassrooms() {
  loading.value = true
  try {
    const res = await classroomApi.list({
      keyword: search.value || undefined,
      page_size: 100,
    })
    classrooms.value = res.data.items
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '加载教室列表失败')
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
  form.value = { name: '', capacity: 20, equipment: [] }
  dialogVisible.value = true
}

function openEditDialog(row: Classroom) {
  isEdit.value = true
  editingId.value = row.id
  form.value = {
    name: row.name,
    capacity: row.capacity,
    equipment: row.equipment || [],
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (isEdit.value && editingId.value) {
      await classroomApi.update(editingId.value, form.value as ClassroomUpdateParams)
      ElMessage.success('教室更新成功')
    } else {
      await classroomApi.create(form.value)
      ElMessage.success('教室创建成功')
    }
    dialogVisible.value = false
    fetchClassrooms()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function toggleStatus(row: Classroom) {
  const newStatus = row.status === 1 ? 0 : 1
  const action = newStatus === 0 ? '维护' : '启用'
  try {
    await ElMessageBox.confirm(`确定要${action}教室「${row.name}」吗？`, '提示', { type: 'warning' })
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
    await ElMessageBox.confirm(`确定要删除教室「${row.name}」吗？此操作不可恢复。`, '警告', { type: 'error' })
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
.classroom-card {
  margin-bottom: 16px;
  border-radius: 12px;
  height: 100%;

  :deep(.el-card__body) {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: 14px 20px;
  }

  .room-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
    flex-shrink: 0;

    .room-name {
      font-size: 18px;
      font-weight: 600;
      color: #1a1a2e;
    }
  }

  .room-info {
    margin-bottom: 6px;

    .info-item {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #606266;
      font-size: 13px;
      margin-bottom: 4px;
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
    gap: 8px;
    padding-top: 8px;
    border-top: 1px solid #ebeef5;
    flex-shrink: 0;
    margin-top: auto;
  }
}
</style>