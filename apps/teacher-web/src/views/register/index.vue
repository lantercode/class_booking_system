<template>
  <div class="register-page">
    <div class="register-card">
      <div class="register-header">
        <div class="logo-icon">
          <el-icon :size="40"><UserFilled /></el-icon>
        </div>
        <h2>教师注册</h2>
        <p>加入舞蹈约课平台，开启教学之旅</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
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

        <el-form-item label="姓名" prop="nickname">
          <el-input
            v-model="form.nickname"
            placeholder="请输入真实姓名"
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
            placeholder="请输入所属机构标识（如：dance-school）"
            :prefix-icon="OfficeBuilding"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            class="submit-btn"
            :loading="loading"
            @click="handleRegister"
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
import { ElMessage } from 'element-plus'
import { UserFilled, Phone, Lock, User, Key, OfficeBuilding } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { apiClient } from '@dance-saas/api-client'

const router = useRouter()

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
    { required: true, message: '请输入姓名', trigger: 'blur' },
    { min: 2, message: '姓名至少2个字符', trigger: 'blur' },
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
    await apiClient.post('/auth/register', {
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
.register-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
  padding: 20px;
}

.register-card {
  width: 100%;
  max-width: 420px;
  background: #fff;
  border-radius: 24px;
  padding: 36px 32px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);

  .register-header {
    text-align: center;
    margin-bottom: 28px;

    .logo-icon {
      width: 64px;
      height: 64px;
      border-radius: 18px;
      background: linear-gradient(135deg, #667eea, #764ba2);
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 14px;
      color: #fff;
    }

    h2 {
      font-size: 22px;
      font-weight: 700;
      color: #1a1a2e;
      margin: 0 0 6px;
    }

    p {
      font-size: 13px;
      color: #909399;
      margin: 0;
    }
  }

  .submit-btn {
    width: 100%;
    border-radius: 14px;
    height: 48px;
    font-size: 16px;
    font-weight: 600;
    background: linear-gradient(135deg, #667eea, #764ba2);
    border: none;
    margin-top: 4px;

    &:hover {
      opacity: 0.9;
    }
  }

  .register-footer {
    text-align: center;
    font-size: 14px;
    color: #909399;
    margin-top: 8px;

    a {
      color: #667eea;
      text-decoration: none;
      margin-left: 4px;
      font-weight: 500;

      &:hover {
        text-decoration: underline;
      }
    }
  }
}
</style>
