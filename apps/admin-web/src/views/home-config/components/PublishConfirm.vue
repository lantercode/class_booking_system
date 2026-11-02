<template>
  <el-dialog
    v-if="visible"
    :model-value="visible"
    title="确认发布首页配置"
    width="480px"
    :close-on-click-modal="true"
    @update:model-value="(v: boolean) => !v && emit('close')"
  >
    <div class="publish-confirm">
      <el-alert
        title="发布后草稿将作为新版本生效，用户小程序会立即看到变更。"
        type="warning"
        show-icon
        :closable="false"
        style="margin-bottom: 16px"
      />

      <div class="changes-summary">
        <h4>本次发布内容概览</h4>
        <div class="changes-list">
          <div v-for="m in sortedModules" :key="m.type" class="change-item">
            <div class="change-left">
              <el-tag :type="moduleTagType(m.type)" size="small" effect="light">
                {{ moduleTypeLabel(m.type) }}
              </el-tag>
            </div>
            <div class="change-right">
              <el-tag v-if="m.enabled" type="success" size="small">已启用</el-tag>
              <el-tag v-else type="info" size="small">已停用</el-tag>
              <span class="change-summary">{{ getSummary(m) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="emit('close')">取消</el-button>
      <el-button type="primary" :loading="loading" @click="emit('confirm')"> 确认发布 </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { HomeConfigModule } from '@dance-saas/api-client'

const props = defineProps<{
  visible: boolean
  modules: HomeConfigModule[]
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'confirm'): void
}>()

const TYPE_LABELS: Record<string, string> = {
  banner: 'Banner 轮播',
  teachers: '师资团队',
  courses: '推荐课程',
  video: '舞蹈视频',
}

const TYPE_TAG_COLORS: Record<string, string> = {
  banner: 'primary',
  teachers: 'success',
  courses: 'warning',
  video: 'danger',
}

function moduleTypeLabel(type: string) {
  return TYPE_LABELS[type] || type
}

function moduleTagType(type: string) {
  return TYPE_TAG_COLORS[type] || ''
}

function getSummary(m: HomeConfigModule): string {
  if (!m.enabled) return '（已停用，不展示）'
  switch (m.type) {
    case 'banner':
      return m.items?.length ? `${m.items.length} 个 Banner` : '未配置内容'
    case 'teachers': {
      const cfg = m.config as any
      return cfg?.teacher_ids?.length ? `已选 ${cfg.teacher_ids.length} 位教师` : '未配置教师'
    }
    case 'courses': {
      const cfg = m.config as any
      return cfg?.course_ids?.length ? `已选 ${cfg.course_ids.length} 门课程` : '未配置课程'
    }
    case 'video': {
      const configured = Array.isArray(m.items)
        ? m.items.filter((it: any) => it?.video_url).length
        : 0
      return configured > 0 ? `${configured} 个视频` : '未配置视频'
    }
    default:
      return ''
  }
}

const sortedModules = computed(() => {
  return [...props.modules].sort((a, b) => (a.sort || 0) - (b.sort || 0))
})
</script>

<style scoped>
.publish-confirm {
  padding: 4px 0;
}

.changes-summary h4 {
  margin: 0 0 12px;
  font-size: 14px;
  color: #303133;
}

.changes-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.change-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: #f8f9fa;
  border-radius: 6px;
}

.change-left {
  flex-shrink: 0;
}

.change-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  font-size: 13px;
}

.change-summary {
  color: #606266;
}
</style>
