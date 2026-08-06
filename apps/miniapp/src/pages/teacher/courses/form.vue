<template>
  <view class="container">
    <view class="header">
      <view class="back-btn" @tap="goBack">
        <text class="back-icon">←</text>
      </view>
      <text class="header-title">{{ isEdit ? '编辑课程' : '创建课程' }}</text>
      <view class="placeholder"></view>
    </view>

    <scroll-view scroll-y class="form-scroll" :show-scrollbar="false">
      <view class="form-area">
        <view class="form-item">
          <text class="label">课程名称 *</text>
          <input
            v-model="form.name"
            type="text"
            placeholder="请输入课程名称"
            class="input"
            @blur="validateName"
          />
          <text v-if="errors.name" class="error-text">{{ errors.name }}</text>
        </view>

        <view class="form-item">
          <text class="label">课程分类</text>
          <view class="category-picker">
            <view
              v-for="cat in categories"
              :key="cat.value"
              class="category-item"
              :class="{ active: form.category === cat.value }"
              @tap="form.category = cat.value"
            >
              <text>{{ cat.label }}</text>
            </view>
          </view>
        </view>

        <view class="form-item">
          <text class="label">课程级别</text>
          <view class="level-picker">
            <view
              v-for="level in levels"
              :key="level.value"
              class="level-item"
              :class="{ active: form.level === level.value }"
              @tap="form.level = level.value"
            >
              <text>{{ level.label }}</text>
            </view>
          </view>
        </view>

        <view class="form-item">
          <text class="label">课程时长(分钟) *</text>
          <view class="number-input-wrapper">
            <view class="number-btn" @tap="form.duration_minutes = Math.max(15, form.duration_minutes - 15)">
              <text>−</text>
            </view>
            <input v-model="form.duration_minutes" type="number" class="number-input" @blur="validateDuration" />
            <view class="number-btn" @tap="form.duration_minutes += 15">
              <text>+</text>
            </view>
          </view>
          <text v-if="errors.duration_minutes" class="error-text">{{ errors.duration_minutes }}</text>
        </view>

        <view class="form-item">
          <text class="label">最大人数 *</text>
          <view class="number-input-wrapper">
            <view class="number-btn" @tap="form.max_capacity = Math.max(1, form.max_capacity - 1)">
              <text>−</text>
            </view>
            <input v-model="form.max_capacity" type="number" class="number-input" @blur="validateCapacity" />
            <view class="number-btn" @tap="form.max_capacity += 1">
              <text>+</text>
            </view>
          </view>
          <text v-if="errors.max_capacity" class="error-text">{{ errors.max_capacity }}</text>
        </view>

        <view class="form-item">
          <text class="label">课程价格(元)</text>
          <view class="price-input-wrapper">
            <text class="price-symbol">¥</text>
            <input v-model="form.price" type="digit" class="price-input" placeholder="0.00" />
          </view>
        </view>

        <view class="form-item">
          <text class="label">所需学分</text>
          <input v-model="form.required_credits" type="number" placeholder="0" class="input" />
        </view>

        <view class="form-item">
          <text class="label">课程描述</text>
          <textarea
            v-model="form.description"
            placeholder="请输入课程描述..."
            class="textarea"
            :maxlength="500"
          />
          <text class="text-count">{{ form.description?.length || 0 }}/500</text>
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
        <text>{{ isLoading ? '提交中...' : (isEdit ? '保存修改' : '创建课程') }}</text>
      </button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { courseApi } from '@/api'
import { AnyARecord } from 'dns'

const isEdit = ref(false)
const courseId = ref(0)
const isLoading = ref(false)

const form = reactive({
  name: '',
  category: '',
  level: '',
  duration_minutes: 60,
  max_capacity: 10,
  price: 0,
  required_credits: 0,
  description: ''
})

const errors = reactive({
  name: '',
  duration_minutes: '',
  max_capacity: ''
})

const categories = [
  { label: '古典舞', value: 'classical' },
  { label: '现代舞', value: 'modern' },
  { label: '爵士舞', value: 'jazz' },
  { label: '拉丁舞', value: 'latin' },
  { label: '街舞', value: 'street' },
  { label: '瑜伽', value: 'yoga' },
  { label: '其他', value: 'other' }
]

const levels = [
  { label: '入门', value: 'beginner' },
  { label: '初级', value: 'elementary' },
  { label: '中级', value: 'intermediate' },
  { label: '高级', value: 'advanced' },
  { label: '专业', value: 'professional' }
]

interface Course {
  name: string
  category?: string
  level?: string
  duration_minutes: number
  max_capacity: number
  price?: number
  required_credits?: number
  description?: string
}

const isFormValid = computed(() => {
  return form.name && form.duration_minutes > 0 && form.max_capacity > 0
})

onMounted(() => {
  const pages = getCurrentPages()
  const options = (pages[pages.length - 1] as any)?.options || {}
  if (options.id) {
    isEdit.value = true
    courseId.value = parseInt(options.id)
    loadCourse()
  }
})

const loadCourse = async () => {
  isLoading.value = true
  try {
    const result = await courseApi.get(courseId.value)
    if (result.code === 0 || result.code === 200) {
      const course = result.data as Course
      form.name = course.name
      form.category = course.category || ''
      form.level = course.level || ''
      form.duration_minutes = course.duration_minutes
      form.max_capacity = course.max_capacity
      form.price = course.price || 0
      form.required_credits = course.required_credits || 0
      form.description = course.description || ''
    }
  } catch {
    uni.showToast({ title: '加载失败', icon: 'none' })
  } finally {
    isLoading.value = false
  }
}

const validateName = () => {
  errors.name = form.name.trim() ? '' : '请输入课程名称'
}

const validateDuration = () => {
  errors.duration_minutes = form.duration_minutes > 0 ? '' : '请输入有效时长'
}

const validateCapacity = () => {
  errors.max_capacity = form.max_capacity > 0 ? '' : '请输入有效人数'
}

const handleSubmit = async () => {
  validateName()
  validateDuration()
  validateCapacity()

  if (!isFormValid.value) return

  isLoading.value = true
  try {
    const data = {
      name: form.name,
      category: form.category || undefined,
      level: form.level || undefined,
      duration_minutes: form.duration_minutes,
      max_capacity: form.max_capacity,
      price: form.price || undefined,
      required_credits: form.required_credits || undefined,
      description: form.description || undefined
    }

    const result = isEdit.value ? await courseApi.update(courseId.value, data) : await courseApi.create(data)

    if (result.code === 0 || result.code === 200) {
      uni.showToast({ title: isEdit.value ? '修改成功' : '创建成功', icon: 'success' })
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

.input {
  width: 100%;
  height: 88rpx;
  background: #f8f8f8;
  border-radius: 12rpx;
  padding: 0 24rpx;
  font-size: 28rpx;
}

.error-text {
  font-size: 24rpx;
  color: #ff4d4f;
  margin-top: 12rpx;
  display: block;
}

.category-picker, .level-picker {
  display: flex;
  flex-wrap: wrap;
}

.category-item, .level-item {
  padding: 16rpx 28rpx;
  background: #f8f8f8;
  border-radius: 40rpx;
  font-size: 26rpx;
  color: #666;
  margin-right: 16rpx;
  margin-bottom: 16rpx;

  &.active {
    background: #667eea;
    color: #fff;
  }
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

.price-input-wrapper {
  display: flex;
  align-items: center;
  background: #f8f8f8;
  border-radius: 12rpx;
  width: 320rpx;
  padding: 0 24rpx;
}

.price-symbol {
  font-size: 28rpx;
  color: #ff4d4f;
  margin-right: 8rpx;
}

.price-input {
  flex: 1;
  height: 88rpx;
  font-size: 32rpx;
}

.textarea {
  width: 100%;
  height: 200rpx;
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
</style>