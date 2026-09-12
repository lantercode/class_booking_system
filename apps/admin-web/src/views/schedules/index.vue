<template>
  <div class="page-container">
    <div class="page-header">
      <h2>排期管理</h2>
      <div style="display:flex;gap:8px;align-items:center">
        <el-input v-model="courseNameFilter" placeholder="搜索课程名称" style="width:180px" clearable @change="handleSearch" @clear="handleSearch" />
        <el-select v-model="teacherFilter" placeholder="筛选教师" style="width:180px" clearable @change="handleSearch">
          <el-option v-for="t in teachers" :key="t.id" :label="t.nickname || t.phone" :value="t.id" />
        </el-select>
        <el-select v-model="statusFilter" placeholder="排期状态" style="width:140px" clearable @change="handleSearch">
          <el-option label="待上课" value="pending" />
          <el-option label="上课中" value="ongoing" />
          <el-option label="已取消" value="cancelled" />
          <el-option label="已完成" value="finished" />
        </el-select>
        <el-date-picker v-model="dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" style="width:260px" @change="handleSearch" />
        <el-button type="primary" @click="showCreateDialog">新增</el-button>
        <el-button type="danger" :disabled="selectedRows.length === 0" @click="handleBatchDelete">
          批量删除
        </el-button>
      </div>
    </div>

    <el-table :data="schedules" stripe v-loading="loading" style="width:100%" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="55" />
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
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.display_status === 1" type="success" size="small">待上课</el-tag>
          <el-tag v-else-if="row.display_status === 2" type="primary" size="small">上课中</el-tag>
          <el-tag v-else-if="row.display_status === 4" type="info" size="small">已完成</el-tag>
          <el-tag v-else-if="row.display_status === 3" type="warning" size="small">已取消</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.display_status === 1" type="primary" size="small" link @click="showEditDialog(row)">编辑</el-button>
          <el-button type="info" size="small" link @click="showStudents(row)">学员</el-button>
          <el-button v-if="row.display_status === 1" type="warning" size="small" link @click="handleCancel(row)">取消</el-button>
          <el-button type="danger" size="small" link @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrapper">
      <el-pagination
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="handlePageChange"
      />
    </div>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑' : '新增'" width="650px" destroy-on-close>
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
          <div style="display:flex;align-items:center;gap:8px;width:100%">
            <el-date-picker v-model="form.start_date" type="date" placeholder="选择日期" style="flex:1" @change="updateSingleEndTime" :disabled-date="disabledSingleDate" />
            <el-tooltip v-if="!isEdit" content="勾选后可选择过去日期，用于补录历史课程数据" placement="top">
              <el-checkbox v-model="allowPastDate" style="white-space:nowrap">补录历史排期</el-checkbox>
            </el-tooltip>
          </div>
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
          <div style="display:flex;align-items:center;gap:8px;width:100%">
            <el-date-picker v-model="batchForm.dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" style="flex:1" :disabled-date="disabledBatchDate" />
            <el-tooltip content="勾选后可选择过去日期，用于补录历史课程数据" placement="top">
              <el-checkbox v-model="allowPastDate" style="white-space:nowrap">补录历史排期</el-checkbox>
            </el-tooltip>
          </div>
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
            <el-tag v-else-if="row.status === 2" type="danger" size="small">已取消</el-tag>
            <el-tag v-else-if="row.status === 3" type="warning" size="small">已签到</el-tag>
            <el-tag v-else-if="row.status === 4" type="info" size="small">已完成</el-tag>
            <el-tag v-else-if="row.status === 5" type="info" size="small">未到场</el-tag>
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

    <el-dialog v-model="cancelVisible" title="取消排期" width="500px" destroy-on-close>
      <el-alert 
        v-if="cancelTarget && cancelTarget.booked_count > 0" 
        type="warning" 
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      >
        <template #title>
          该排期已有 {{ cancelTarget.booked_count }} 名学员预约
        </template>
        <div>
          <p style="margin: 8px 0">取消后将:</p>
          <ul style="margin: 0; padding-left: 20px">
            <li>自动取消所有学员的预约</li>
            <li>课时将退还至学员会员卡</li>
            <li>发送取消通知给所有学员</li>
          </ul>
        </div>
      </el-alert>
      
      <el-form :model="cancelForm" label-width="100px">
        <el-form-item label="取消原因" required>
          <el-select v-model="cancelForm.reason" placeholder="请选择取消原因" style="width:100%">
            <el-option label="老师临时有事" value="老师临时有事" />
            <el-option label="教室不可用" value="教室不可用" />
            <el-option label="天气原因" value="天气原因" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        
        <el-form-item v-if="cancelForm.reason === '其他'" label="详细说明">
          <el-input 
            v-model="cancelForm.detail" 
            type="textarea" 
            :rows="3"
            placeholder="请输入详细取消原因"
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="cancelVisible = false">取消</el-button>
        <el-button type="warning" @click="confirmCancel" :loading="cancelling">
          确认取消
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Plus, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { scheduleApi, courseApi, classroomApi, userApi, bookingApi, type Schedule } from '@dance-saas/api-client'

const loading = ref(false)
const submitting = ref(false)
const batchDeleting = ref(false)
const schedules = ref<Schedule[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const dateRange = ref<any[]>([])
const teacherFilter = ref<number | null>(null)
const courseNameFilter = ref('')
const statusFilter = ref<string | null>(null)
const selectedRows = ref<Schedule[]>([])

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

function formatDateTime(date: Date, timeStr: string): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d} ${timeStr}`
}

function disabledSingleDate(time: Date) {
  if (allowPastDate.value) return false
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return time.getTime() < today.getTime()
}

function disabledBatchDate(time: Date) {
  if (allowPastDate.value) return false
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return time.getTime() < today.getTime()
}

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
    if (teacherFilter.value) {
      params.teacher_id = teacherFilter.value
    }
    if (courseNameFilter.value) {
      params.course_name = courseNameFilter.value
    }
    if (statusFilter.value === 'pending') {
      params.display_status = 1
    } else if (statusFilter.value === 'ongoing') {
      params.display_status = 2
    } else if (statusFilter.value === 'cancelled') {
      params.display_status = 3
    } else if (statusFilter.value === 'finished') {
      params.display_status = 4
    }
    if (dateRange.value && dateRange.value.length === 2) {
      params.start_from = formatDateTime(dateRange.value[0], '00:00:00')
      params.start_to = formatDateTime(dateRange.value[1], '23:59:59')
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
const allowPastDate = ref(false)
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
  allowPastDate.value = false
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
  
  // 处理时间
  let hours = 0, minutes = 0
  if (form.value.start_time instanceof Date) {
    hours = form.value.start_time.getHours()
    minutes = form.value.start_time.getMinutes()
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

  if (!isEdit.value && !allowPastDate.value) {
    const selectedDate = new Date(form.value.start_date!)
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    
    if (selectedDate < today) {
      ElMessage.error('不能选择过去的日期创建排期，如需补录历史排期请勾选"补录历史排期"')
      return
    }

    const startAt = new Date(form.value.start_date!)
    startAt.setHours(form.value.start_time!.getHours(), form.value.start_time!.getMinutes(), 0, 0)
    
    if (startAt < new Date()) {
      ElMessage.error('不能选择过去的时间创建排期，如需补录历史排期请勾选"补录历史排期"')
      return
    }
  }

  // 验证课程时长
  if (form.value.course_id && form.value.start_date && form.value.start_time && form.value.end_time) {
    const startAt = new Date(form.value.start_date!)
    startAt.setHours(form.value.start_time!.getHours(), form.value.start_time!.getMinutes(), 0, 0)
    const endAt = new Date(form.value.start_date!)
    endAt.setHours(form.value.end_time!.getHours(), form.value.end_time!.getMinutes(), 0, 0)
    
    const courseDuration = getCourseDuration(form.value.course_id)
    const scheduleDuration = Math.round((endAt.getTime() - startAt.getTime()) / 60000)
    
    if (courseDuration !== scheduleDuration) {
      ElMessage.error(`排期时长(${scheduleDuration}分钟)与课程时长(${courseDuration}分钟)不匹配，请调整结束时间`)
      return
    }
  }

  submitting.value = true
  try {
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

const cancelVisible = ref(false)
const cancelling = ref(false)
const cancelTarget = ref<Schedule | null>(null)
const cancelForm = ref({
  reason: '',
  detail: '',
})

function handleCancel(row: Schedule) {
  cancelTarget.value = row
  cancelForm.value = { reason: '', detail: '' }
  cancelVisible.value = true
}

async function confirmCancel() {
  if (!cancelForm.value.reason) {
    ElMessage.warning('请选择取消原因')
    return
  }
  
  const reason = cancelForm.value.reason === '其他' 
    ? cancelForm.value.detail 
    : cancelForm.value.reason
  
  if (!reason) {
    ElMessage.warning('请输入详细取消原因')
    return
  }

  cancelling.value = true
  try {
    const res = await scheduleApi.cancel(cancelTarget.value!.id, { cancel_reason: reason })
    const result = res.data
    
    if (result.total_bookings > 0) {
      ElMessage.success(`排期已取消，已处理 ${result.success_count}/${result.total_bookings} 个学员预约，课时已退还`)
    } else {
      ElMessage.success('排期已取消')
    }
    
    cancelVisible.value = false
    fetchSchedules()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '取消失败')
  } finally {
    cancelling.value = false
  }
}

async function handleDelete(row: Schedule) {
  try {
    const courseName = getCourseName(row.course_id)
    const dateStr = formatDate(row.start_at)
    const timeStr = formatTime(row.start_at)
    
    await ElMessageBox.confirm(
      `确定要删除「${courseName} ${dateStr} ${timeStr}」吗？删除后将无法恢复！`,
      '删除确认',
      { type: 'warning' }
    )
    await scheduleApi.delete(row.id)
    ElMessage.success('排期已删除')
    fetchSchedules()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.msg || '删除失败')
    }
  }
}

function handleSelectionChange(rows: Schedule[]) {
  selectedRows.value = rows
}

async function handleBatchDelete() {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请选择要删除的排期')
    return
  }

  const selectedCount = selectedRows.value.length
  // 仅检查待上课状态的排期是否有学员预约
  const hasBookedNormalRows = selectedRows.value.filter(r => r.status === 1 && r.booked_count > 0)

  if (hasBookedNormalRows.length > 0) {
    ElMessage.warning(`选中的 ${selectedCount} 个排期中，有 ${hasBookedNormalRows.length} 个待上课排期已有学员预约，请先取消排期后再删除`)
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要批量删除选中的 ${selectedCount} 个排期吗？删除后将无法恢复！`,
      '批量删除确认',
      { type: 'warning' }
    )
  } catch {
    return
  }

  batchDeleting.value = true
  try {
    const ids = selectedRows.value.map(r => r.id)
    const res = await scheduleApi.batchDelete(ids)
    const result = res.data
    
    if (result.failed_count > 0) {
      ElMessage.warning(`批量删除完成：成功 ${result.success_count} 个，失败 ${result.failed_count} 个`)
      if (result.errors && result.errors.length > 0) {
        console.error('删除失败详情:', result.errors)
      }
    } else {
      ElMessage.success(`成功删除 ${result.success_count} 个排期`)
    }
    
    selectedRows.value = []
    fetchSchedules()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '批量删除失败')
  } finally {
    batchDeleting.value = false
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
  const now = allowPastDate.value ? new Date(0) : new Date()
  
  const previews: typeof batchPreview.value = []
  
  let currentDate = new Date(startDate)
  while (currentDate <= endDate) {
    const dayOfWeek = currentDate.getDay().toString()
    if (weekdays.includes(dayOfWeek)) {
      const startAt = new Date(currentDate)
      startAt.setHours(startTime.getHours(), startTime.getMinutes(), 0, 0)
      const endAt = new Date(startAt.getTime() + duration * 60000)
      
      if (startAt >= now) {
        previews.push({
          date: currentDate.toLocaleDateString('zh-CN'),
          time: `${startAt.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })} - ${endAt.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`,
          teacher: getTeacherName(teacher_id),
          classroom: getClassroomName(classroom_id),
          start_at: startAt.toISOString(),
          end_at: endAt.toISOString(),
        })
      }
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