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
      <el-table-column type="index" label="序号" width="60" />
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
          <el-tag v-if="row.status === 1" type="success" size="small">启用</el-tag>
          <el-tag v-else-if="row.status === 0" type="danger" size="small">禁用</el-tag>
          <el-tag v-else-if="row.status === 2" type="warning" size="small">已取消</el-tag>
          <el-tag v-else-if="row.status === 3" type="info" size="small">已完成</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" link @click="showEditDialog(row)" :disabled="row.status !== 1">编辑</el-button>
          <el-button type="info" size="small" link @click="showStudents(row)">学员</el-button>
          <el-button v-if="row.status === 1" type="warning" size="small" link @click="handleDisable(row)">禁用</el-button>
          <el-button v-else-if="row.status === 0" type="success" size="small" link @click="handleEnable(row)">启用</el-button>
          <el-button v-if="row.status !== 1" type="danger" size="small" link @click="handleDelete(row)">删除</el-button>
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑排期' : '新增排期'" width="650px" destroy-on-close>
      <div v-if="!isEdit" style="margin-bottom:16px">
        <el-radio-group v-model="scheduleMode">
          <el-radio label="single">单条排期</el-radio>
          <el-radio label="batch">批量排期</el-radio>
        </el-radio-group>
      </div>

      <!-- 单条排期表单 -->
      <el-form v-if="isEdit || scheduleMode === 'single'" :model="form" label-width="100px" :rules="rules" ref="formRef">
        <el-form-item label="课程" prop="course_id">
          <el-select v-model="form.course_id" placeholder="请选择课程" style="width:100%" @change="onCourseChange">
            <el-option v-for="c in courses" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="教师" prop="teacher_id">
          <el-select v-model="form.teacher_id" placeholder="请选择教师" style="width:100%">
            <el-option v-for="t in teachers" :key="t.id" :label="t.nickname || t.phone" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="教室" prop="classroom_id">
          <el-select v-model="form.classroom_id" placeholder="请选择教室" style="width:100%">
            <el-option v-for="r in classrooms" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期" prop="start_date">
          <el-date-picker v-model="form.start_date" type="date" placeholder="选择日期" style="width:100%" @change="updateSingleEndTime" />
        </el-form-item>
        <el-form-item label="开始时间" prop="start_time">
          <el-time-picker v-model="form.start_time" placeholder="选择开始时间" style="width:100%" format="HH:mm" @change="updateSingleEndTime" />
        </el-form-item>
        <el-form-item label="结束时间">
          <el-time-picker v-model="form.end_time" placeholder="根据开始时间和时长自动计算" style="width:100%" format="HH:mm" disabled />
        </el-form-item>
        <el-form-item label="容量" prop="capacity">
          <el-input-number v-model="form.capacity" :min="1" :max="200" style="width:100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
      </el-form>

      <!-- 批量排期表单 -->
      <el-form v-if="scheduleMode === 'batch'" :model="batchForm" label-width="100px" :rules="batchRules" ref="batchFormRef">
        <el-form-item label="课程" prop="course_id">
          <el-select v-model="batchForm.course_id" placeholder="请选择课程" style="width:100%" @change="onBatchCourseChange">
            <el-option v-for="c in courses" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="教师" prop="teacher_id">
          <el-select v-model="batchForm.teacher_id" placeholder="请选择教师" style="width:100%">
            <el-option v-for="t in teachers" :key="t.id" :label="t.nickname || t.phone" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="教室" prop="classroom_id">
          <el-select v-model="batchForm.classroom_id" placeholder="请选择教室" style="width:100%">
            <el-option v-for="r in classrooms" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期范围" prop="dateRange">
          <el-date-picker v-model="batchForm.dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" style="width:100%" />
        </el-form-item>
        <el-form-item label="重复模式" prop="weekdays">
          <el-checkbox-group v-model="batchForm.weekdays">
            <el-checkbox label="1">周一</el-checkbox>
            <el-checkbox label="2">周二</el-checkbox>
            <el-checkbox label="3">周三</el-checkbox>
            <el-checkbox label="4">周四</el-checkbox>
            <el-checkbox label="5">周五</el-checkbox>
            <el-checkbox label="6">周六</el-checkbox>
            <el-checkbox label="0">周日</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="开始时间" prop="startTime">
          <el-time-picker v-model="batchForm.startTime" placeholder="选择开始时间" style="width:100%" format="HH:mm" @change="updateBatchEndTime" />
        </el-form-item>
        <el-form-item label="结束时间">
          <el-time-picker v-model="batchForm.endTime" placeholder="根据开始时间和时长自动计算" style="width:100%" format="HH:mm" disabled />
        </el-form-item>
        <el-form-item label="容量" prop="capacity">
          <el-input-number v-model="batchForm.capacity" :min="1" :max="200" style="width:100%" />
        </el-form-item>
      </el-form>

      <!-- 批量排期预览 -->
      <div v-if="scheduleMode === 'batch' && batchPreview.length > 0" style="margin-top:20px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <span style="font-weight:600">排期预览（共 {{ batchPreview.length }} 条）</span>
          <el-button size="small" @click="batchPreview = []">清空</el-button>
        </div>
        <el-table :data="batchPreview" size="small" style="width:100%">
          <el-table-column prop="date" label="日期" width="100" />
          <el-table-column prop="time" label="时间" width="140" />
          <el-table-column prop="teacher" label="教师" width="100" />
          <el-table-column prop="classroom" label="教室" width="100" />
        </el-table>
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <template v-if="isEdit || scheduleMode === 'single'">
          <el-button type="primary" @click="handleSingleSubmit" :loading="submitting">确定</el-button>
        </template>
        <template v-else>
          <el-button v-if="batchPreview.length === 0" type="info" @click="generatePreview">生成预览</el-button>
          <el-button v-else type="primary" @click="handleBatchSubmit" :loading="batchSubmitting">确认创建</el-button>
        </template>
      </template>
    </el-dialog>

    <el-dialog v-model="studentDialogVisible" title="学员列表" width="500px" destroy-on-close>
      <el-table :data="studentList" stripe v-loading="studentLoading" size="small" style="width:100%">
        <el-table-column label="学员" width="180">
          <template #default="{ row }">{{ row.student_nickname || `学员#${row.student_id}` }}</template>
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

const courses = ref<{ id: number; name: string; duration_minutes: number }[]>([])
const teachers = ref<{ id: number; nickname: string | null; phone: string }[]>([])
const classrooms = ref<{ id: number; name: string }[]>([])

const courseMap = ref<Record<number, string>>({})
const courseDurationMap = ref<Record<number, number>>({})
const teacherMap = ref<Record<number, string>>({})
const classroomMap = ref<Record<number, string>>({})

function getCourseName(id: number) { return courseMap.value[id] || `课程#${id}` }
function getCourseDuration(id: number) { return courseDurationMap.value[id] || 0 }
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
    courseDurationMap.value = {}
    for (const c of courses.value) {
      courseMap.value[c.id] = c.name
      courseDurationMap.value[c.id] = c.duration_minutes
    }
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
const scheduleMode = ref<'single' | 'batch'>('single')
const formRef = ref()
const form = ref({
  id: 0,
  course_id: null as number | null,
  teacher_id: null as number | null,
  classroom_id: null as number | null,
  start_date: null as Date | null,
  start_time: null as Date | null,
  end_time: null as Date | null,
  capacity: 20,
  notes: '',
})

const rules = {
  course_id: [{ required: true, message: '请选择课程', trigger: 'change' }],
  teacher_id: [{ required: true, message: '请选择教师', trigger: 'change' }],
  classroom_id: [{ required: true, message: '请选择教室', trigger: 'change' }],
  start_date: [{ required: true, message: '请选择日期', trigger: 'change' }],
  start_time: [{ required: true, message: '请选择开始时间', trigger: 'change' }],
  capacity: [{ required: true, message: '请输入容量', trigger: 'blur' }],
}

function showCreateDialog() {
  isEdit.value = false
  scheduleMode.value = 'single'
  form.value = { id: 0, course_id: null, teacher_id: null, classroom_id: null, start_date: null, start_time: null, end_time: null, capacity: 20, notes: '' }
  dialogVisible.value = true
}

function showEditDialog(row: Schedule) {
  isEdit.value = true
  const startAt = new Date(row.start_at)
  const endAt = new Date(row.end_at)
  form.value = {
    id: row.id,
    course_id: row.course_id,
    teacher_id: row.teacher_id,
    classroom_id: row.classroom_id,
    start_date: new Date(startAt.toDateString()),
    start_time: startAt,
    end_time: endAt,
    capacity: row.capacity,
    notes: row.notes || '',
  }
  dialogVisible.value = true
}

function onCourseChange() {
  updateSingleEndTime()
}

function updateSingleEndTime() {
  console.log('updateSingleEndTime called', {
    course_id: form.value.course_id,
    start_date: form.value.start_date,
    start_time: form.value.start_time,
    duration: form.value.course_id ? getCourseDuration(form.value.course_id) : 'N/A'
  })
  
  if (!form.value.course_id) {
    console.log('No course selected')
    return
  }
  
  if (!form.value.start_date) {
    console.log('No start date selected')
    return
  }
  
  if (!form.value.start_time) {
    console.log('No start time selected')
    return
  }
  
  const duration = getCourseDuration(form.value.course_id)
  if (duration <= 0) {
    console.warn('Course duration is 0 or invalid')
    return
  }
  
  // 处理日期可能是字符串的情况
  const startDate = typeof form.value.start_date === 'string' 
    ? new Date(form.value.start_date) 
    : form.value.start_date
  
  // 处理时间可能是字符串的情况
  let hours = 0, minutes = 0
  if (form.value.start_time instanceof Date) {
    hours = form.value.start_time.getHours()
    minutes = form.value.start_time.getMinutes()
  } else if (typeof form.value.start_time === 'string') {
    const timeParts = form.value.start_time.split(':')
    hours = parseInt(timeParts[0], 10) || 0
    minutes = parseInt(timeParts[1], 10) || 0
  }
  
  const startAt = new Date(startDate)
  startAt.setHours(hours, minutes, 0, 0)
  const endAt = new Date(startAt.getTime() + duration * 60000)
  
  console.log('Calculated end time:', endAt)
  form.value.end_time = endAt
}

async function handleSingleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  // 验证课程时长
  if (form.value.course_id && form.value.start_date && form.value.start_time && form.value.end_time) {
    const startAt = new Date(form.value.start_date)
    startAt.setHours(form.value.start_time.getHours(), form.value.start_time.getMinutes(), 0, 0)
    const endAt = new Date(form.value.start_date)
    endAt.setHours(form.value.end_time.getHours(), form.value.end_time.getMinutes(), 0, 0)
    
    const courseDuration = getCourseDuration(form.value.course_id)
    const scheduleDuration = Math.round((endAt.getTime() - startAt.getTime()) / 60000)
    
    if (courseDuration !== scheduleDuration) {
      ElMessage.error(`排期时长(${scheduleDuration}分钟)与课程时长(${courseDuration}分钟)不匹配，请调整结束时间`)
      return
    }
  }

  submitting.value = true
  try {
    // 合并日期和时间
    const startAt = new Date(form.value.start_date!)
    startAt.setHours(form.value.start_time!.getHours(), form.value.start_time!.getMinutes(), 0, 0)
    const endAt = new Date(form.value.start_date!)
    endAt.setHours(form.value.end_time!.getHours(), form.value.end_time!.getMinutes(), 0, 0)
    
    const payload: any = {
      course_id: form.value.course_id,
      teacher_id: form.value.teacher_id,
      classroom_id: form.value.classroom_id || undefined,
      start_at: startAt.toISOString(),
      end_at: endAt.toISOString(),
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

async function handleDisable(row: Schedule) {
  try {
    const courseName = getCourseName(row.course_id)
    const dateStr = formatDate(row.start_at)
    const timeStr = formatTime(row.start_at)
    await ElMessageBox.confirm(`确定要禁用「${courseName} ${dateStr} ${timeStr}」吗？`, '禁用确认', { type: 'warning' })
    await scheduleApi.update(row.id, { status: 0 })
    ElMessage.success('排期已禁用')
    fetchSchedules()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.msg || '禁用失败')
    }
  }
}

async function handleEnable(row: Schedule) {
  try {
    const courseName = getCourseName(row.course_id)
    const dateStr = formatDate(row.start_at)
    const timeStr = formatTime(row.start_at)
    await ElMessageBox.confirm(`确定要启用「${courseName} ${dateStr} ${timeStr}」吗？`, '启用确认', { type: 'warning' })
    await scheduleApi.update(row.id, { status: 1 })
    ElMessage.success('排期已启用')
    fetchSchedules()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.msg || '启用失败')
    }
  }
}

async function handleDelete(row: Schedule) {
  try {
    const courseName = getCourseName(row.course_id)
    const dateStr = formatDate(row.start_at)
    const timeStr = formatTime(row.start_at)
    await ElMessageBox.confirm(`确定要删除「${courseName} ${dateStr} ${timeStr}」吗？删除后将无法恢复！`, '删除确认', { type: 'warning' })
    await scheduleApi.delete(row.id)
    ElMessage.success('排期已删除')
    fetchSchedules()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.msg || '删除失败')
    }
  }
}

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

const batchSubmitting = ref(false)
const batchFormRef = ref()
const batchForm = ref({
  course_id: null as number | null,
  dateRange: [] as Date[],
  weekdays: [] as string[],
  startTime: null as Date | null,
  endTime: null as Date | null,
  teacher_id: null as number | null,
  classroom_id: null as number | null,
  capacity: 20,
})

const batchRules = {
  course_id: [{ required: true, message: '请选择课程', trigger: 'change' }],
  dateRange: [{ required: true, message: '请选择日期范围', trigger: 'change' }],
  weekdays: [{ required: true, message: '请选择重复日期', trigger: 'change' }],
  startTime: [{ required: true, message: '请选择开始时间', trigger: 'change' }],
  teacher_id: [{ required: true, message: '请选择教师', trigger: 'change' }],
  classroom_id: [{ required: true, message: '请选择教室', trigger: 'change' }],
  capacity: [{ required: true, message: '请输入容量', trigger: 'blur' }],
}

const batchPreview = ref<{ date: string; time: string; teacher: string; classroom: string; start_at: string; end_at: string }[]>([])

const batchEndTime = ref('')

function onBatchCourseChange() {
  updateBatchEndTime()
}

function updateBatchEndTime() {
  if (batchForm.value.course_id && batchForm.value.startTime) {
    const duration = getCourseDuration(batchForm.value.course_id)
    const endTime = new Date(batchForm.value.startTime.getTime() + duration * 60000)
    batchForm.value.endTime = endTime
  }
}

async function generatePreview() {
  const valid = await batchFormRef.value?.validate().catch(() => false)
  if (!valid) return

  const { course_id, dateRange, weekdays, startTime, teacher_id, classroom_id, capacity } = batchForm.value
  
  if (!course_id || !dateRange || dateRange.length !== 2 || !weekdays.length || !startTime || !teacher_id) {
    ElMessage.error('请填写完整信息')
    return
  }

  const duration = getCourseDuration(course_id)
  const startDate = dateRange[0]
  const endDate = dateRange[1]
  
  const previews: typeof batchPreview.value = []
  
  let currentDate = new Date(startDate)
  while (currentDate <= endDate) {
    const dayOfWeek = currentDate.getDay().toString()
    if (weekdays.includes(dayOfWeek)) {
      const startAt = new Date(currentDate)
      startAt.setHours(startTime.getHours(), startTime.getMinutes(), 0, 0)
      const endAt = new Date(startAt.getTime() + duration * 60000)
      
      previews.push({
        date: currentDate.toLocaleDateString('zh-CN'),
        time: `${startAt.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })} - ${endAt.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`,
        teacher: getTeacherName(teacher_id),
        classroom: getClassroomName(classroom_id),
        start_at: startAt.toISOString(),
        end_at: endAt.toISOString(),
      })
    }
    currentDate.setDate(currentDate.getDate() + 1)
  }

  if (previews.length === 0) {
    ElMessage.warning('在指定日期范围内没有符合条件的日期')
    return
  }

  batchPreview.value = previews
}

async function handleBatchSubmit() {
  if (batchPreview.value.length === 0) {
    ElMessage.error('请先生成排期预览')
    return
  }

  batchSubmitting.value = true
  try {
    const items = batchPreview.value.map(p => ({
      course_id: batchForm.value.course_id!,
      teacher_id: batchForm.value.teacher_id!,
      classroom_id: batchForm.value.classroom_id || undefined,
      start_at: p.start_at,
      end_at: p.end_at,
      capacity: batchForm.value.capacity,
    }))
    
    await scheduleApi.batchCreate(items)
    ElMessage.success(`成功创建 ${batchPreview.value.length} 个排期`)
    dialogVisible.value = false
    batchPreview.value = []
    fetchSchedules()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '批量创建失败')
  } finally {
    batchSubmitting.value = false
  }
}

onMounted(() => {
  fetchLookups()
  fetchSchedules()
})
</script>