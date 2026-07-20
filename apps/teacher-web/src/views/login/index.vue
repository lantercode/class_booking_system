<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <div class="logo-icon">
          <el-icon :size="40"><UserFilled /></el-icon>
        </div>
        <h2>教师登录</h2>
        <p>舞蹈约课系统 · 教师端</p>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="0" size="large">
        <el-form-item prop="phone">
          <el-input v-model="form.phone" placeholder="请输入手机号" :prefix-icon="Phone" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-form-item prop="tenant_slug">
          <el-input
            v-model="form.tenant_slug"
            placeholder="请输入机构标识（如：dance-school）"
            :prefix-icon="OfficeBuilding"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" class="submit-btn" :loading="loading" @click="handleLogin">
            登录
          </el-button>
        </el-form-item>
      </el-form>
      <div class="login-footer">
        <span>没有账号？</span>
        <router-link to="/register">立即注册</router-link>
        <span class="divider">|</span>
        <span class="switch-link" @click="goToStudentLogin">学员端</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { UserFilled, Phone, Lock, OfficeBuilding } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  phone: '',
  password: '',
  tenant_slug: '',
})

const rules: FormRules = {
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' },
  ],
}

async function handleLogin() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await authStore.login({ phone: form.phone, password: form.password, tenant_slug: form.tenant_slug || undefined })
    ElMessage.success('登录成功')
    const redirect = (route.query.redirect as string) || '/courses'
    router.push(redirect)
  } catch {
    ElMessage.error('登录失败，请检查账号密码')
  } finally {
    loading.value = false
  }
}

function goToStudentLogin() {
  window.open('http://localhost:5173/login', '_blank')
}
</script>

<style scoped lang="scss">
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
  padding: 20px;
}

.login-card {
  width: 100%;
  max-width: 400px;
  background: #fff;
  border-radius: 24px;
  padding: 40px 32px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);

  .login-header {
    text-align: center;
    margin-bottom: 32px;

    .logo-icon {
      width: 72px;
      height: 72px;
      border-radius: 20px;
      background: linear-gradient(135deg, #667eea, #764ba2);
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 16px;
      color: #fff;
    }

    h2 {
      font-size: 24px;
      font-weight: 700;
      color: #1a1a2e;
      margin: 0 0 8px;
    }

    p {
      font-size: 14px;
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

    &:hover {
      opacity: 0.9;
    }
  }

  .login-footer {
    text-align: center;
    margin-top: 16px;
    font-size: 13px;
    color: #909399;

    a {
      color: #667eea;
      font-weight: 500;
      margin: 0 4px;

      &:hover {
        text-decoration: underline;
      }
    }

    .divider {
      margin: 0 6px;
      color: #dcdfe6;
    }

    .switch-link {
      color: #667eea;
      cursor: pointer;

      &:hover {
        text-decoration: underline;
      }
    }
  }
}
</style>