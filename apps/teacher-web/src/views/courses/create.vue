<template>
  <div class="create-container">
    <header class="page-header">
      <el-button text @click="$router.back()">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
      <span class="header-title">{{ isEdit ? '编辑课程' : '创建课程' }}</span>
      <div style="width: 60px"></div>
    </header>

    <div class="form-wrapper">
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
      >
        <el-form-item label="课程名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入课程名称" maxlength="30" show-word-limit />
        </el-form-item>

        <el-form-item label="课程描述" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="4"
            placeholder="请输入课程描述"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="难度等级" prop="difficulty">
              <el-select v-model="form.difficulty" placeholder="请选择">
                <el-option label="入门" value="beginner" />
                <el-option label="中级" value="intermediate" />
                <el-option label="高级" value="advanced" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="课程时长(分钟)" prop="duration">
              <el-input-number
                v-model="form.duration"
                :min="30"
                :max="240"
                :step="15"
                class="w-full"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="价格(元/节)" prop="price">
              <el-input-number
                v-model="form.price"
                :min="0"
                :max="9999"
                :step="10"
                class="w-full"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="班级容量(人)" prop="capacity">
              <el-input-number
                v-model="form.capacity"
                :min="1"
                :max="100"
                class="w-full"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="课程标签" prop="tags">
          <el-select
            v-model="form.tags"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="添加标签"
          >
            <el-option label="古典舞" value="古典舞" />
            <el-option label="街舞" value="街舞" />
            <el-option label="芭蕾" value="芭蕾" />
            <el-option label="拉丁" value="拉丁" />
            <el-option label="现代舞" value="现代舞" />
            <el-option label="零基础" value="零基础" />
            <el-option label="进阶" value="进阶" />
            <el-option label="热门" value="热门" />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            class="submit-btn"
            :loading="submitting"
            @click="handleSubmit"
          >
            {{ isEdit ? '保存修改' : '创建课程' }}
          </el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { courseApi, type CourseCreateParams } from '@dance-saas/api-client'

const route = useRoute()
const router = useRouter()
const formRef = ref<FormInstance>()
const submitting = ref(false)

const isEdit = computed(() => !!route.params.id)

const LEVEL_REVERSE_MAP: Record<string, string> = {
  beginner: '入门',
  intermediate: '中级',
  advanced: '高级',
}

const form = reactive({
  name: '',
  description: '',
  difficulty: 'beginner' as string,
  duration: 60,
  price: 120,
  capacity: 15,
  tags: [] as string[],
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入课程名称', trigger: 'blur' }],
  description: [{ required: true, message: '请输入课程描述', trigger: 'blur' }],
  difficulty: [{ required: true, message: '请选择难度等级', trigger: 'change' }],
}

onMounted(async () => {
  if (isEdit.value) {
    const id = Number(route.params.id)
    try {
      const res = await courseApi.getById(id)
      const c = res.data
      form.name = c.name
      form.description = c.description || ''
      form.difficulty = LEVEL_REVERSE_MAP[c.level || ''] || 'beginner'
      form.duration = c.duration_minutes
      form.price = c.price
      form.capacity = c.max_capacity
      form.tags = [c.category, c.level].filter(Boolean) as string[]
    } catch {
      ElMessage.error('加载课程信息失败')
    }
  }
})

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const data: CourseCreateParams = {
      name: form.name,
      description: form.description,
      level: LEVEL_REVERSE_MAP[form.difficulty],
      duration_minutes: form.duration,
      max_capacity: form.capacity,
      price: form.price,
    }
    if (isEdit.value) {
      const id = Number(route.params.id)
      await courseApi.update(id, data)
      ElMessage.success('课程已更新')
    } else {
      await courseApi.create(data)
      ElMessage.success('课程已创建')
    }
    router.push('/courses')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '操作失败')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped lang="scss">
.create-container {
  min-height: 100vh;
  background: linear-gradient(180deg, #fef5f9 0%, #f0f2ff 30%, #f5f7fa 100%);
  max-width: 800px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.04);
  position: sticky;
  top: 0;
  z-index: 50;

  .header-title {
    font-size: 17px;
    font-weight: 700;
    color: #1a1a2e;
  }
}

.form-wrapper {
  background: #fff;
  margin: 16px;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}

.cover-preview {
  margin-top: 12px;
  border-radius: 12px;
  overflow: hidden;
  height: 180px;

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
}

.w-full {
  width: 100%;
}

.submit-btn {
  width: 100%;
  border-radius: 14px;
  height: 48px;
  font-size: 16px;
  font-weight: 600;
  background: linear-gradient(135deg, #667eea, #764ba2);
  border: none;
  margin-top: 8px;
}
</style>