<template>
  <div class="register-container">
    <div class="register-card">
      <h2 class="register-title">创建账号</h2>
      <p class="register-subtitle">注册学员账号，开始约课</p>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent="handleRegister"
      >
        <el-form-item label="手机号" prop="phone">
          <el-input
            v-model="form.phone"
            placeholder="请输入手机号"
            :prefix-icon="Phone"
            maxlength="11"
          />
        </el-form-item>

        <el-form-item label="昵称" prop="nickname">
          <el-input
            v-model="form.nickname"
            placeholder="请输入昵称"
            :prefix-icon="User"
            maxlength="20"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码（至少6位）"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>

        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="请再次输入密码"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>

        <el-form-item label="验证码" prop="verify_code">
          <el-input
            v-model="form.verify_code"
            placeholder="请输入验证码（开发环境输入 000000）"
            :prefix-icon="Key"
            maxlength="6"
          />
        </el-form-item>

        <el-form-item label="机构标识" prop="tenant_slug">
          <el-input
            v-model="form.tenant_slug"
            placeholder="请输入机构标识（如：dance-school）"
            :prefix-icon="OfficeBuilding"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            native-type="submit"
            :loading="loading"
            class="register-btn"
          >
            {{ loading ? '注册中...' : '注 册' }}
          </el-button>
        </el-form-item>
      </el-form>

      <div class="register-footer">
        <span>已有账号？</span>
        <router-link to="/login">立即登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Phone, Lock, User, OfficeBuilding, Key } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  phone: '',
  nickname: '',
  password: '',
  confirmPassword: '',
  verify_code: '',
  tenant_slug: '',
})

const validateConfirmPassword = (_rule: any, value: string, callback: any) => {
  if (value !== form.password) {
    callback(new Error('两次密码不一致'))
  } else {
    callback()
  }
}

const rules: FormRules = {
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '手机号格式不正确', trigger: 'blur' },
  ],
  nickname: [
    { required: true, message: '请输入昵称', trigger: 'blur' },
    { min: 2, message: '昵称至少2个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
  verify_code: [
    { required: true, message: '请输入验证码', trigger: 'blur' },
    { min: 4, message: '验证码至少4位', trigger: 'blur' },
  ],
  tenant_slug: [
    { required: true, message: '请输入机构标识', trigger: 'blur' },
  ],
}

async function handleRegister() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await userStore.register({
      phone: form.phone,
      nickname: form.nickname,
      password: form.password,
      verify_code: form.verify_code,
      tenant_slug: form.tenant_slug,
    })

    ElMessage.success('注册成功，请登录')
    router.push('/login')
  } catch (err: any) {
    const msg = err.response?.data?.detail || err.response?.data?.message || '注册失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.register-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.register-card {
  width: 420px;
  padding: 40px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
}

.register-title {
  text-align: center;
  font-size: 24px;
  color: #303133;
  margin-bottom: 4px;
}

.register-subtitle {
  text-align: center;
  font-size: 14px;
  color: #909399;
  margin-bottom: 32px;
}

.register-btn {
  width: 100%;
  height: 44px;
  font-size: 16px;
}

.register-footer {
  text-align: center;
  font-size: 14px;
  color: #909399;

  a {
    color: #667eea;
    text-decoration: none;
    margin-left: 4px;

    &:hover {
      text-decoration: underline;
    }
  }
}
</style>