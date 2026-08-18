<template>
  <view class="container">
    <view class="header">
      <view class="back-btn" @tap="goBack">
        <text class="back-icon">←</text>
      </view>
      <text class="header-title">{{ isEdit ? '编辑排期' : '添加排期' }}</text>
      <view class="placeholder"></view>
    </view>

    <scroll-view scroll-y class="form-scroll" :show-scrollbar="false">
      <view class="form-area">
        <view class="form-item">
          <text class="label">选择课程 *</text>
          <view class="picker-wrapper" @tap="showCoursePicker = true">
            <text class="picker-value">{{ selectedCourse?.name || '请选择课程' }}</text>
            <text class="picker-arrow">▼</text>
          </view>
          <text v-if="errors.course" class="error-text">{{ errors.course }}</text>
        </view>

        <view class="form-item">
          <text class="label">上课日期 *</text>
          <picker mode="date" :value="form.start_date" @change="onDateChange">
            <view class="picker-wrapper">
              <text class="picker-value">{{ form.start_date || '请选择日期' }}</text>
              <text class="picker-arrow">▼</text>
            </view>
          </picker>
          <text v-if="errors.date" class="error-text">{{ errors.date }}</text>
        </view>

        <view class="form-item">
          <text class="label">开始时间 *</text>
          <picker mode="time" :value="form.start_time" @change="onStartTimeChange">
            <view class="picker-wrapper">
              <text class="picker-value">{{ form.start_time || '请选择开始时间' }}</text>
              <text class="picker-arrow">▼</text>
            </view>
          </picker>
          <text v-if="errors.startTime" class="error-text">{{ errors.startTime }}</text>
        </view>

        <view class="form-item">
          <text class="label">结束时间 *</text>
          <picker mode="time" :value="form.end_time" @change="onEndTimeChange">
            <view class="picker-wrapper">
              <text class="picker-value">{{ form.end_time || '请选择结束时间' }}</text>
              <text class="picker-arrow">▼</text>
            </view>
          </picker>
          <text v-if="errors.endTime" class="error-text">{{ errors.endTime }}</text>
        </view>

        <view class="form-item">
          <text class="label">上课人数 *</text>
          <view class="number-input-wrapper">
            <view class="number-btn" @tap="form.capacity = Math.max(1, form.capacity - 1)">
              <text>−</text>
            </view>
            <input v-model="form.capacity" type="number" class="number-input" @blur="validateCapacity" />
            <view class="number-btn" @tap="form.capacity += 1">
              <text>+</text>
            </view>
          </view>
          <text v-if="errors.capacity" class="error-text">{{ errors.capacity }}</text>
        </view>

        <view class="form-item">
          <text class="label">备注</text>
          <textarea
            v-model="form.notes"
            placeholder="添加备注信息..."
            class="textarea"
            :maxlength="200"
          />
          <text class="text-count">{{ form.notes?.length || 0 }}/200</text>
        </view>
      </view>
    </scroll-view>

    <view class="footer">
      <button
        class="submit-btn"
        :class="{ disabled: !isFormValid }"
        :disabled="!isFormValid || isLoading"
        @tap="handleSubmit"
      >
        <text v-if="isLoading" class="loading">⏳</text>
        <text>{{ isLoading ? '提交中...' : (isEdit ? '保存修改' : '添加排期') }}</text>
      </button>
    </view>

    <view v-if="showCoursePicker" class="modal-overlay" @tap="showCoursePicker = false">
      <view class="picker-modal" @tap.stop>
        <view class="modal-header">
          <text class="modal-title">选择课程</text>
          <view class="close-btn" @tap="showCoursePicker = false">
            <text>✕</text>
          </view>
        </view>
        <scroll-view scroll-y class="picker-list" :show-scrollbar="false">
          <view
            v-for="course in courses"
            :key="course.id"
            class="picker-item"
            :class="{ active: selectedCourse?.id === course.id }"
            @tap="selectCourse(course)"
          >
            <text>{{ course.name }}</text>
          </view>
        </scroll-view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { teacherApi, scheduleApi } from '@/api'
import { extractList } from '@/utils/helpers'

const isEdit = ref(false)
const scheduleId = ref(0)
const isLoading = ref(false)
const showCoursePicker = ref(false)

// ✅ 页面卸载标记
let isUnmounted = false

const courses = ref<any[]>([])
const selectedCourse = ref<any>(null)

const form = reactive({
  start_date: '',
  start_time: '',
  end_time: '',
  capacity: 10,
  notes: ''
})

const errors = reactive({
  course: '',
  date: '',
  startTime: '',
  endTime: '',
  capacity: ''
})

const isFormValid = computed(() => {
  return selectedCourse.value && form.start_date && form.start_time && form.end_time && form.capacity > 0
})

onMounted(() => {
  loadCourses()

  const pages = getCurrentPages()
  const options = (pages[pages.length - 1] as any)?.options || {}
  if (options.id) {
    isEdit.value = true
    scheduleId.value = parseInt(options.id)
    loadSchedule()
  }
})

onUnmounted(() => {
  isUnmounted = true
})

const loadCourses = async () => {
  try {
    const result = await teacherApi.getCourses()
    
    // ✅ 页面已卸载，不再更新数据
    if (isUnmounted) return
    
    courses.value = extractList(result)
  } catch {
    uni.showToast({ title: '加载课程失败', icon: 'none' })
  }
}

const loadSchedule = async () => {
  isLoading.value = true
  try {
    const result = await scheduleApi.get(scheduleId.value)
    
    // ✅ 页面已卸载，不再更新数据
    if (isUnmounted) return
    
    if (result.code === 0 || result.code === 200) {
      const schedule = result.data
      selectedCourse.value = { id: schedule.course_id, name: schedule.course_name }
      
      const startDate = new Date(schedule.start_at)
      const endDate = new Date(schedule.end_at)
      
      form.start_date = startDate.toISOString().split('T')[0]
      form.start_time = `${String(startDate.getHours()).padStart(2, '0')}:${String(startDate.getMinutes()).padStart(2, '0')}`
      form.end_time = `${String(endDate.getHours()).padStart(2, '0')}:${String(endDate.getMinutes()).padStart(2, '0')}`
      form.capacity = schedule.capacity
      form.notes = schedule.notes || ''
    }
  } catch {
    uni.showToast({ title: '加载失败', icon: 'none' })
  } finally {
    isLoading.value = false
  }
}

const selectCourse = (course: any) => {
  selectedCourse.value = course
  showCoursePicker.value = false
}

const onDateChange = (e: any) => {
  form.start_date = e.detail.value
}

const onStartTimeChange = (e: any) => {
  form.start_time = e.detail.value
}

const onEndTimeChange = (e: any) => {
  form.end_time = e.detail.value
}

const validateCapacity = () => {
  errors.capacity = form.capacity > 0 ? '' : '请输入有效人数'
}

const handleSubmit = async () => {
  errors.course = selectedCourse.value ? '' : '请选择课程'
  errors.date = form.start_date ? '' : '请选择日期'
  errors.startTime = form.start_time ? '' : '请选择开始时间'
  errors.endTime = form.end_time ? '' : '请选择结束时间'
  validateCapacity()

  if (!isFormValid.value) return

  isLoading.value = true
  try {
    const startDateTime = new Date(`${form.start_date}T${form.start_time}:00`)
    const endDateTime = new Date(`${form.start_date}T${form.end_time}:00`)

    const data = {
      course_id: selectedCourse.value.id,
      teacher_id: getTeacherId(),
      start_at: startDateTime.toISOString(),
      end_at: endDateTime.toISOString(),
      capacity: form.capacity,
      notes: form.notes || undefined
    }

    const result = isEdit.value ? await scheduleApi.update(scheduleId.value, data) : await scheduleApi.create(data)

    if (result.code === 0 || result.code === 200) {
      uni.showToast({ title: isEdit.value ? '修改成功' : '添加成功', icon: 'success' })
      setTimeout(() => uni.navigateBack(), 1500)
    } else {
      uni.showToast({ title: result.msg || '提交失败', icon: 'none' })
    }
  } catch {
    uni.showToast({ title: '提交失败', icon: 'none' })
  } finally {
    isLoading.value = false
  }
}

const getTeacherId = () => {
  const userInfo = uni.getStorageSync('user_info')
  return userInfo ? JSON.parse(userInfo).id : 0
}

const goBack = () => {
  uni.navigateBack()
}
</script>

<style lang="scss">
/* ✅ 已通过 vite.config.ts 全局注入 scrollbar 样式 */
.container {
  height: 100vh;             // ✅ 使用固定高度
  background: #f5f5f5;
  display: flex;
  flex-direction: column;
  overflow: hidden;          // ✅ 防止外层滚动
}

.header {
  flex-shrink: 0;            // ✅ 头部不被压缩
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 60rpx 32rpx 24rpx;
  background: #fff;
}

.back-btn {
  width: 64rpx;
  height: 64rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.back-icon {
  font-size: 40rpx;
}

.header-title {
  font-size: 34rpx;
  font-weight: bold;
}

.placeholder {
  width: 64rpx;
}

.form-scroll {
  flex: 1;                   // ✅ 现在能正确计算高度
  height: 0;                 // ✅ 关键：让 flex:1 正确计算
  padding: 24rpx;
  padding-bottom: 120rpx;    // ✅ 底部留白（保存按钮区域）
  box-sizing: border-box;
}

.form-area {
  background: #fff;
  border-radius: 16rpx;
  padding: 32rpx;
}

.form-item {
  margin-bottom: 28rpx;
}

.label {
  font-size: 28rpx;
  color: #333;
  margin-bottom: 16rpx;
  display: block;
}

.picker-wrapper {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 88rpx;
  background: #f8f8f8;
  border-radius: 12rpx;
  padding: 0 24rpx;
}

.picker-value {
  font-size: 28rpx;
}

.picker-arrow {
  font-size: 24rpx;
  color: #999;
}

.error-text {
  font-size: 24rpx;
  color: #ff4d4f;
  margin-top: 12rpx;
  display: block;
}

.number-input-wrapper {
  display: flex;
  align-items: center;
  background: #f8f8f8;
  border-radius: 12rpx;
  width: 320rpx;
}

.number-btn {
  width: 80rpx;
  height: 88rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36rpx;
  color: #667eea;
  border-right: 1rpx solid #e0e0e0;

  &:last-child {
    border-right: none;
    border-left: 1rpx solid #e0e0e0;
  }
}

.number-input {
  flex: 1;
  height: 88rpx;
  text-align: center;
  font-size: 32rpx;
}

.textarea {
  width: 100%;
  height: 160rpx;
  background: #f8f8f8;
  border-radius: 12rpx;
  padding: 20rpx 24rpx;
  font-size: 28rpx;
}

.text-count {
  font-size: 24rpx;
  color: #999;
  text-align: right;
  margin-top: 12rpx;
  display: block;
}

.footer {
  padding: 24rpx 32rpx 48rpx;
  background: #fff;
  border-top: 1rpx solid #f0f0f0;
}

.submit-btn {
  width: 100%;
  height: 96rpx;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 16rpx;
  border: none;
  color: #fff;
  font-size: 32rpx;
  font-weight: bold;
  display: flex;
  align-items: center;
  justify-content: center;

  &.disabled {
    opacity: 0.5;
  }
}

.loading {
  margin-right: 12rpx;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: flex-end;
  z-index: 1000;
}

.picker-modal {
  width: 100%;
  background: #fff;
  border-radius: 20rpx 20rpx 0 0;
  max-height: 70vh;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 32rpx;
  border-bottom: 1rpx solid #f0f0f0;
}

.modal-title {
  font-size: 32rpx;
  font-weight: bold;
}

.close-btn {
  width: 48rpx;
  height: 48rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32rpx;
  color: #999;
}

.picker-list {
  max-height: 60vh;
  padding: 16rpx 0;
}

.picker-item {
  padding: 28rpx 32rpx;
  font-size: 28rpx;

  &.active {
    background: #f0f5ff;
    color: #667eea;
  }
}
</style>