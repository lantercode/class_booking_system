<template>
  <div class="page-container">
    <div class="page-header">
      <h2>排期管理</h2>
      <div style="display:flex;gap:8px">
        <el-date-picker v-model="dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" style="width:260px" @change="handleSearch" />
        <el-button type="primary" @click="showCreateDialog"><el-icon><Plus /></el-icon>新增排期</el-button>
      </div>
    </div>

    <el-table :data="schedules" stripe v-loading="loading" style="width:100%">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column label="课程" width="140">
        <template #default="{ row }">{{ getCourseName(row.course_id) }}</template>
      </el-table-column>
      <el-table-column label="教师" width="100">
        <template #default="{ row }">{{ getTeacherName(row.teacher_id) }}</template>
      </el-table-column>
      <el-table-column label="教室" width="100">
        <template #default="{ row }">{{ getClassroomName(row.classroom_id) }}</template>
      </el-table-column>
      <el-table-column label="日期" width="120">
        <template #default="{ row }">{{ formatDate(row.start_at) }}</template>
      </el-table-column>
      <el-table-column label="时间" width="160">
        <template #default="{ row }">{{ formatTime(row.start_at) }} - {{ formatTime(row.end_at) }}</template>
      </el-table-column>
      <el-table-column label="预约" width="140">
        <template #default="{ row }">
          <el-progress :percentage="row.capacity ? Math.round(row.booked_count / row.capacity * 100) : 0" :color="row.booked_count >= row.capacity ? '#f56c6c' : '#667eea'" />
          <span style="font-size:12px;color:#909399">{{ row.booked_count }}/{{ row.capacity }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag v-if="row.status === 1" type="success" size="small">正常</el-tag>
          <el-tag v-else-if="row.status === 2" type="danger" size="small">已取消</el-tag>
          <el-tag v-else-if="row.status === 3" type="info" size="small">已完成</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" link @click="showEditDialog(row)" :disabled="row.status !== 1">编辑</el-button>
          <el-button type="info" size="small" link @click="showStudents(row)">学员</el-button>
          <el-button type="danger" size="small" link @click="handleCancel(row)" :disabled="row.status !== 1">取消</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div style="display:flex;justify-content:center;margin-top:20px">
      <el-pagination
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="handlePageChange"
      />
    </div>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑排期' : '新增排期'" width="550px" destroy-on-close>
      <el-form :model="form" label-width="100px" :rules="rules" ref="formRef">
        <el-form-item label="课程" prop="course_id">
          <el-select v-model="form.course_id" placeholder="请选择课程" style="width:100%">
            <el-option v-for="c in courses" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="教师" prop="teacher_id">
          <el-select v-model="form.teacher_id" placeholder="请选择教师" style="width:100%">
            <el-option v-for="t in teachers" :key="t.id" :label="t.nickname || t.phone" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="教室" prop="classroom_id">
          <el-select v-model="form.classroom_id" placeholder="请选择教室" style="width:100%" clearable>
            <el-option v-for="r in classrooms" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始时间" prop="start_at">
          <el-date-picker v-model="form.start_at" type="datetime" placeholder="选择开始时间" style="width:100%" />
        </el-form-item>
        <el-form-item label="结束时间" prop="end_at">
          <el-date-picker v-model="form.end_at" type="datetime" placeholder="选择结束时间" style="width:100%" />
        </el-form-item>
        <el-form-item label="容量" prop="capacity">
          <el-input-number v-model="form.capacity" :min="1" :max="200" style="width:100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="studentDialogVisible" title="学员列表" width="500px" destroy-on-close>
      <el-table :data="studentList" stripe v-loading="studentLoading" size="small" style="width:100%">
        <el-table-column label="学员" width="180">
          <template #default="{ row }">{{ teacherMap[row.student_id] || `学员#${row.student_id}` }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.status === 1" type="success" size="small">已预约</el-tag>
            <el-tag v-else-if="row.status === 2" type="warning" size="small">已签到</el-tag>
            <el-tag v-else-if="row.status === 3" type="info" size="small">已完成</el-tag>
            <el-tag v-else-if="row.status === 0" type="danger" size="small">已取消</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="预约时间" width="160">
          <template #default="{ row }">{{ formatTime(row.booked_at) }}</template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="studentDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { scheduleApi, courseApi, classroomApi, userApi, bookingApi, type Schedule } from '@dance-saas/api-client'

const loading = ref(false)
const submitting = ref(false)
const schedules = ref<Schedule[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const dateRange = ref<any[]>([])

const courses = ref<{ id: number; name: string }[]>([])
const teachers = ref<{ id: number; nickname: string | null; phone: string }[]>([])
const classrooms = ref<{ id: number; name: string }[]>([])

const courseMap = ref<Record<number, string>>({})
const teacherMap = ref<Record<number, string>>({})
const classroomMap = ref<Record<number, string>>({})

function getCourseName(id: number) { return courseMap.value[id] || `课程#${id}` }
function getTeacherName(id: number) { return teacherMap.value[id] || `教师#${id}` }
function getClassroomName(id: number | null) { return id ? (classroomMap.value[id] || `教室#${id}`) : '-' }

function formatDate(iso: string) { return iso?.slice(0, 10) || '' }
function formatTime(iso: string) { return iso ? new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '' }

async function fetchLookups() {
  try {
    const [cCourses, cClassrooms, cUsers] = await Promise.all([
      courseApi.list({ page_size: 100 }),
      classroomApi.list({ page_size: 100 }),
      userApi.list({ page_size: 100, role_code: 'teacher' }),
    ])
    courses.value = cCourses.data.items
    classrooms.value = cClassrooms.data.items
    teachers.value = cUsers.data.items

    courseMap.value = {}
    for (const c of courses.value) courseMap.value[c.id] = c.name
    classroomMap.value = {}
    for (const r of classrooms.value) classroomMap.value[r.id] = r.name
    teacherMap.value = {}
    for (const t of teachers.value) teacherMap.value[t.id] = t.nickname || t.phone
  } catch (_) {}
}

async function fetchSchedules() {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize.value }
    if (dateRange.value && dateRange.value.length === 2) {
      params.start_from = dateRange.value[0].toISOString()
      params.start_to = new Date(dateRange.value[1].getTime() + 86400000).toISOString()
    }
    const res = await scheduleApi.list(params)
    schedules.value = res.data.items
    total.value = res.data.total
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '加载排期列表失败')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  fetchSchedules()
}

function handlePageChange(p: number) {
  page.value = p
  fetchSchedules()
}

const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref()
const form = ref({
  id: 0,
  course_id: null as number | null,
  teacher_id: null as number | null,
  classroom_id: null as number | null,
  start_at: null as Date | null,
  end_at: null as Date | null,
  capacity: 20,
  notes: '',
})

const rules = {
  course_id: [{ required: true, message: '请选择课程', trigger: 'change' }],
  teacher_id: [{ required: true, message: '请选择教师', trigger: 'change' }],
  start_at: [{ required: true, message: '请选择开始时间', trigger: 'change' }],
  end_at: [{ required: true, message: '请选择结束时间', trigger: 'change' }],
  capacity: [{ required: true, message: '请输入容量', trigger: 'blur' }],
}

function showCreateDialog() {
  isEdit.value = false
  form.value = { id: 0, course_id: null, teacher_id: null, classroom_id: null, start_at: null, end_at: null, capacity: 20, notes: '' }
  dialogVisible.value = true
}

function showEditDialog(row: Schedule) {
  isEdit.value = true
  form.value = {
    id: row.id,
    course_id: row.course_id,
    teacher_id: row.teacher_id,
    classroom_id: row.classroom_id,
    start_at: new Date(row.start_at),
    end_at: new Date(row.end_at),
    capacity: row.capacity,
    notes: row.notes || '',
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const payload: any = {
      course_id: form.value.course_id,
      teacher_id: form.value.teacher_id,
      classroom_id: form.value.classroom_id || undefined,
      start_at: form.value.start_at?.toISOString(),
      end_at: form.value.end_at?.toISOString(),
      capacity: form.value.capacity,
      notes: form.value.notes || undefined,
    }
    if (isEdit.value) {
      await scheduleApi.update(form.value.id, payload)
      ElMessage.success('排期更新成功')
    } else {
      await scheduleApi.create(payload)
      ElMessage.success('排期创建成功')
    }
    dialogVisible.value = false
    fetchSchedules()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function handleCancel(row: Schedule) {
  try {
    await ElMessageBox.confirm(`确定要取消排期 #${row.id} 吗？`, '取消确认', { type: 'warning' })
    await scheduleApi.cancel(row.id)
    ElMessage.success('排期已取消')
    fetchSchedules()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.msg || '取消失败')
    }
  }
}

onMounted(() => {
  fetchLookups()
  fetchSchedules()
})

const studentDialogVisible = ref(false)
const studentLoading = ref(false)
const studentList = ref<any[]>([])

async function showStudents(row: Schedule) {
  studentDialogVisible.value = true
  studentLoading.value = true
  try {
    const res = await bookingApi.list({ schedule_id: row.id, page_size: 100 })
    studentList.value = res.data.items
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '加载学员列表失败')
  } finally {
    studentLoading.value = false
  }
}
</script>