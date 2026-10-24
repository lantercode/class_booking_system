<template>
  <div class="page-container tenant-page">
    <div class="page-header">
      <h2>机构设置</h2>
    </div>

    <div class="tenant-content">
      <!-- 加载失败：错误态 + 重试 -->
      <el-card v-if="loadError" shadow="never" class="error-card">
        <el-result icon="error" title="加载机构信息失败" :sub-title="loadError">
          <template #extra>
            <el-button type="primary" @click="loadAll">重试</el-button>
          </template>
        </el-result>
      </el-card>

      <template v-else>
        <!-- 机构基本信息 -->
        <el-card shadow="never" class="section-card" v-loading="loading" element-loading-text="加载中...">
          <template #header>
            <span class="section-title">机构信息</span>
          </template>
          <el-form
            ref="infoFormRef"
            :model="infoForm"
            :rules="infoRules"
            label-width="100px"
            label-position="left"
          >
            <el-form-item label="机构名称" prop="name">
              <el-input v-model="infoForm.name" placeholder="请输入机构名称" maxlength="100" show-word-limit />
            </el-form-item>
            <el-form-item label="机构标识">
              <el-input :model-value="infoForm.slug" disabled />
              <div class="field-hint">机构标识不可修改，用于登录和 API 访问</div>
            </el-form-item>
            <el-form-item label="Logo URL" prop="logo_url">
              <el-input v-model="infoForm.logo_url" placeholder="可选，留空则不设置" maxlength="500" />
            </el-form-item>
            <el-form-item label="联系电话" prop="contact_phone">
              <el-input v-model="infoForm.contact_phone" placeholder="可选" maxlength="20" />
            </el-form-item>
            <el-form-item label="联系邮箱" prop="contact_email">
              <el-input v-model="infoForm.contact_email" placeholder="可选" maxlength="100" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="infoSaving" @click="saveInfo">
                保存机构信息
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- 预约配置 -->
        <el-card shadow="never" class="section-card" v-loading="loading" element-loading-text="加载中...">
          <template #header>
            <span class="section-title">预约配置</span>
          </template>
          <el-form :model="settingsForm" label-width="100px" label-position="left">
            <el-form-item label="提前预约天数">
              <el-input-number v-model="settingsForm.booking_advance_days" :min="1" :max="90" />
              <span class="field-hint inline-hint">学员最多可提前预约的天数（1-90）</span>
            </el-form-item>
            <el-form-item label="取消规则">
              <el-input-number v-model="settingsForm.booking_cancel_minutes" :min="1" :max="480" />
              <span class="field-hint inline-hint">课前多少分钟内不可取消预约（1-480）</span>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="settingsSaving" @click="saveSettings">
                保存设置
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { tenantApi, type TenantInfo, type TenantInfoUpdate, type TenantSettingsUpdate } from '@dance-saas/api-client'

// ------------------------------------------------------------
// 状态
// ------------------------------------------------------------

const loading = ref(false)
const loadError = ref('')
const infoSaving = ref(false)
const settingsSaving = ref(false)

const infoFormRef = ref<FormInstance>()

// 机构信息表单（slug 仅用于只读展示，不提交）
const infoForm = reactive({
  name: '',
  slug: '',
  logo_url: '',
  contact_phone: '',
  contact_email: '',
})

// 预约配置表单
const settingsForm = reactive({
  booking_advance_days: 1,
  booking_cancel_minutes: 90,
})

// 初始快照（用于 dirty 检测，实现 exclude_unset 语义：只提交变更字段）
let infoSnapshot: Omit<TenantInfo, 'id'> | null = null
let settingsSnapshot: { booking_advance_days: number; booking_cancel_minutes: number } | null = null

const infoRules: FormRules = {
  name: [{ required: true, message: '请输入机构名称', trigger: 'blur' }],
  contact_email: [{ type: 'email', message: '邮箱格式不正确', trigger: 'blur' }],
}

// ------------------------------------------------------------
// 加载
// ------------------------------------------------------------

async function loadAll() {
  loading.value = true
  loadError.value = ''
  try {
    const [settingsRes, infoRes] = await Promise.all([
      tenantApi.getSettings(),
      tenantApi.getInfo(),
    ])

    // settings
    settingsForm.booking_advance_days = settingsRes.data.booking_advance_days
    settingsForm.booking_cancel_minutes = settingsRes.data.booking_cancel_minutes
    settingsSnapshot = { ...settingsForm }

    // info
    infoForm.name = infoRes.data.name
    infoForm.slug = infoRes.data.slug
    infoForm.logo_url = infoRes.data.logo_url ?? ''
    infoForm.contact_phone = infoRes.data.contact_phone ?? ''
    infoForm.contact_email = infoRes.data.contact_email ?? ''
    infoSnapshot = {
      name: infoRes.data.name,
      slug: infoRes.data.slug,
      logo_url: infoRes.data.logo_url,
      contact_phone: infoRes.data.contact_phone,
      contact_email: infoRes.data.contact_email,
    }
  } catch (e: any) {
    loadError.value = e?.response?.data?.msg || '请检查网络或稍后重试'
  } finally {
    loading.value = false
  }
}

// ------------------------------------------------------------
// 保存：预约配置（只提交变更字段）
// ------------------------------------------------------------

async function saveSettings() {
  if (!settingsSnapshot) return

  const payload: TenantSettingsUpdate = {}
  if (settingsForm.booking_advance_days !== settingsSnapshot.booking_advance_days) {
    payload.booking_advance_days = settingsForm.booking_advance_days
  }
  if (settingsForm.booking_cancel_minutes !== settingsSnapshot.booking_cancel_minutes) {
    payload.booking_cancel_minutes = settingsForm.booking_cancel_minutes
  }

  if (Object.keys(payload).length === 0) {
    ElMessage.info('没有需要保存的更改')
    return
  }

  settingsSaving.value = true
  try {
    const res = await tenantApi.updateSettings(payload)
    settingsForm.booking_advance_days = res.data.booking_advance_days
    settingsForm.booking_cancel_minutes = res.data.booking_cancel_minutes
    settingsSnapshot = { ...settingsForm }
    ElMessage.success('预约配置已保存')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '保存预约配置失败')
  } finally {
    settingsSaving.value = false
  }
}

// ------------------------------------------------------------
// 保存：机构信息（name 必传，其余仅提交变更字段）
// ------------------------------------------------------------

async function saveInfo() {
  if (!infoFormRef.value || !infoSnapshot) return
  const valid = await infoFormRef.value.validate().catch(() => false)
  if (!valid) return

  const payload: TenantInfoUpdate = { name: infoForm.name }

  // 可选字段：与快照比较（null 统一按 '' 处理），仅提交变更
  const originalLogo = infoSnapshot.logo_url ?? ''
  const originalPhone = infoSnapshot.contact_phone ?? ''
  const originalEmail = infoSnapshot.contact_email ?? ''

  if (infoForm.logo_url !== originalLogo) {
    payload.logo_url = infoForm.logo_url
  }
  if (infoForm.contact_phone !== originalPhone) {
    payload.contact_phone = infoForm.contact_phone
  }
  if (infoForm.contact_email !== originalEmail) {
    payload.contact_email = infoForm.contact_email
  }

  if (
    payload.name === infoSnapshot.name &&
    payload.logo_url === undefined &&
    payload.contact_phone === undefined &&
    payload.contact_email === undefined
  ) {
    ElMessage.info('没有需要保存的更改')
    return
  }

  infoSaving.value = true
  try {
    const res = await tenantApi.updateInfo(payload)
    // 用后端返回的最新值回填表单与快照
    infoForm.name = res.data.name
    infoForm.slug = res.data.slug
    infoForm.logo_url = res.data.logo_url ?? ''
    infoForm.contact_phone = res.data.contact_phone ?? ''
    infoForm.contact_email = res.data.contact_email ?? ''
    infoSnapshot = {
      name: res.data.name,
      slug: res.data.slug,
      logo_url: res.data.logo_url,
      contact_phone: res.data.contact_phone,
      contact_email: res.data.contact_email,
    }
    // 清掉上一次校验状态
    infoFormRef.value.clearValidate()
    ElMessage.success('机构信息已保存')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '保存机构信息失败')
  } finally {
    infoSaving.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped lang="scss">
.tenant-content {
  flex: 1;
  overflow-y: auto;
  padding-right: 4px;

  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: #dcdfe6;
    border-radius: 2px;
    transition: background 0.3s;
  }

  &::-webkit-scrollbar-thumb:hover {
    background: #c0c4cc;
  }
}

.section-card {
  max-width: 640px;
  margin-bottom: 16px;
}

.error-card {
  max-width: 640px;
}

.section-title {
  font-weight: 600;
  font-size: 15px;
}

.field-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.inline-hint {
  display: inline-block;
  margin-top: 0;
  margin-left: 8px;
}
</style>
