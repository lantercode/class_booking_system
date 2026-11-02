<template>
  <div class="page-container">
    <div class="page-header">
      <h2>小程序首页配置</h2>
      <div class="header-actions">
        <el-button :loading="publishing" type="primary" @click="showPublishConfirm">
          <el-icon><Upload /></el-icon>
          发布
        </el-button>
        <el-button @click="openPreview">
          <el-icon><View /></el-icon>
          预览
        </el-button>
        <el-button @click="fetchDraft">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <div v-if="loadError" class="list-error-block">
      <el-result icon="error" title="加载配置失败" :sub-title="loadError">
        <template #extra>
          <el-button type="primary" @click="fetchDraft">重试</el-button>
        </template>
      </el-result>
    </div>

    <el-card v-else v-loading="loading" class="config-card">
      <template #header>
        <div class="card-header">
          <span>首页模块列表</span>
          <div class="header-info">
            <el-tag v-if="hasChanges" type="warning" size="small">有未发布变更</el-tag>
            <el-tag v-else type="success" size="small">已同步</el-tag>
            <span class="version-info">
              草稿 v{{ draftData?.version || '-' }} / 已发布 v{{ publishedVersion || '-' }}
            </span>
          </div>
        </div>
      </template>

      <el-alert
        title="拖拽左侧手柄可调整模块顺序，修改后点击右上角「发布」生效"
        type="info"
        show-icon
        :closable="false"
        style="margin-bottom: 16px"
      />

      <el-table ref="tableRef" :data="modules" row-key="type" stripe style="width: 100%">
        <el-table-column width="50" align="center">
          <template #default>
            <el-icon class="drag-handle"><Rank /></el-icon>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="140">
          <template #default="{ row }">
            <el-tag :type="moduleTagType(row.type)" effect="light" round>
              {{ moduleTypeLabel(row.type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="摘要" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="module-summary">{{ getModuleSummary(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="是否启用" width="100" align="center">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" @change="(val: boolean) => handleToggle(row, val)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="openEdit(row)"> 编辑 </el-button>
            <el-button type="warning" size="small" link @click="resetModule(row)"> 重置 </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="autoSaving" class="auto-save-tip">
        <el-icon class="is-loading"><Loading /></el-icon>
        自动保存草稿中...
      </div>
    </el-card>

    <!-- 编辑抽屉 -->
    <ModuleDrawer
      v-if="drawerVisible"
      :visible="drawerVisible"
      :module="editingModule"
      @close="drawerVisible = false"
      @save="handleDrawerSave"
    />

    <!-- 预览弹窗 -->
    <el-dialog
      v-model="previewVisible"
      title="小程序首页预览"
      width="440px"
      top="5vh"
      :close-on-click-modal="true"
    >
      <MiniAppPreview :modules="modules" />
    </el-dialog>

    <!-- 发布确认弹窗 -->
    <PublishConfirm
      v-if="publishConfirmVisible"
      :visible="publishConfirmVisible"
      :modules="modules"
      :loading="publishing"
      @close="publishConfirmVisible = false"
      @confirm="handlePublish"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import Sortable from 'sortablejs'
import {
  CircleCheckFilled,
  CircleCloseFilled,
  Loading,
  Rank,
  Refresh,
  Upload,
  View,
} from '@element-plus/icons-vue'
import { homeConfigApi, type HomeConfigModule } from '@dance-saas/api-client'
import ModuleDrawer from './components/ModuleDrawer.vue'
import MiniAppPreview from './components/MiniAppPreview.vue'
import PublishConfirm from './components/PublishConfirm.vue'

const loading = ref(false)
const loadError = ref('')
const publishing = ref(false)
const autoSaving = ref(false)
const publishConfirmVisible = ref(false)
const drawerVisible = ref(false)
const previewVisible = ref(false)
const editingModule = ref<HomeConfigModule | null>(null)

const draftData = ref<any>(null)
const publishedVersion = ref<number | null>(null)

const modules = ref<HomeConfigModule[]>([])

// 当前模块副本（避免直接改 draftData.modules）
const VALID_TYPES = ['banner', 'teachers', 'courses', 'video']

function syncFromDraft() {
  if (draftData.value?.payload?.modules) {
    // 过滤掉已废弃的 type（如 notice），并确保 4 种 type 都存在
    const filtered = draftData.value.payload.modules.filter((m: any) =>
      VALID_TYPES.includes(m.type)
    )
    const existingTypes = new Set(filtered.map((m: any) => m.type))
    VALID_TYPES.forEach((type, i) => {
      if (!existingTypes.has(type)) {
        filtered.push({ type, enabled: type !== 'notice', sort: filtered.length + 1 })
      }
    })
    filtered.sort((a: any, b: any) => a.sort - b.sort)
    // 兼容旧草稿：video 单条 config 结构归一为 items[]，保证列表摘要与抽屉编辑内容一致
    const normalized = filtered.map((m: any) => {
      if (m.type === 'video' && !Array.isArray(m.items)) {
        const cfg = m.config || {}
        m.items = cfg.video_url
          ? [
              {
                title: cfg.title || '',
                description: cfg.description || '',
                cover_url: cfg.cover_url || '',
                video_url: cfg.video_url,
              },
            ]
          : []
        delete m.config
      }
      return m
    })
    modules.value = JSON.parse(JSON.stringify(normalized))
  } else {
    // 初始空配置
    modules.value = [
      { type: 'banner', enabled: true, sort: 1, items: [] },
      { type: 'teachers', enabled: true, sort: 2 },
      { type: 'courses', enabled: true, sort: 3 },
      { type: 'video', enabled: true, sort: 4 },
    ]
  }
}

const hasChanges = computed(() => {
  return draftData.value?.has_changes === true
})

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

function moduleBadgeType(type: string) {
  // 根据模块类型返回不同徽章颜色
  const map: Record<string, string> = {
    banner: 'primary',
    teachers: 'success',
    courses: 'warning',
    video: 'danger',
  }
  return map[type] || 'primary'
}

function getModuleSummary(m: HomeConfigModule): string {
  switch (m.type) {
    case 'banner':
      return m.items && m.items.length > 0 ? `已配置 ${m.items.length} 个 Banner` : '未配置'
    case 'teachers': {
      const cfg = m.config as any
      const ids = cfg?.teacher_ids?.length || 0
      return ids > 0 ? `已选 ${ids} 位教师` : '未配置'
    }
    case 'courses': {
      const cfg = m.config as any
      const ids = cfg?.course_ids?.length || 0
      return ids > 0 ? `已选 ${ids} 门课程` : '未配置'
    }
    case 'video': {
      const configured = Array.isArray(m.items)
        ? m.items.filter((it: any) => it?.video_url).length
        : 0
      return configured > 0 ? `已配置 ${configured} 个视频` : '未配置'
    }
    default:
      return '未知类型'
  }
}

async function fetchDraft() {
  loading.value = true
  loadError.value = ''
  try {
    const res = await homeConfigApi.getHomeConfigDraft()
    draftData.value = res.data
    syncFromDraft()
    // 读取已发布版本号（从 draft 响应可能拿不到，通过 versions 接口）
    try {
      const verRes = await homeConfigApi.listHomeConfigVersions()
      publishedVersion.value = verRes.data.items?.[0]?.version ?? null
    } catch {
      // 忽略版本列表错误
    }
  } catch (e: any) {
    loadError.value = e?.msg || e?.response?.data?.msg || '加载配置失败'
    ElMessage.error(loadError.value)
  } finally {
    loading.value = false
  }
}

function buildPayload() {
  // 重建 sort 值
  const sortedModules = modules.value.map((m, i) => ({
    ...m,
    sort: i + 1,
  }))
  return {
    schema_version: 1,
    modules: sortedModules,
  }
}

async function saveDraft(silent = false) {
  autoSaving.value = true
  try {
    await homeConfigApi.updateHomeConfigDraft(buildPayload())
    // 更新本地 has_changes
    const res = await homeConfigApi.getHomeConfigDraft()
    draftData.value = res.data
    syncFromDraft()
    if (!silent) {
      ElMessage.success('草稿已保存')
    }
  } catch (e: any) {
    ElMessage.error(e?.msg || e?.response?.data?.msg || '保存草稿失败')
  } finally {
    autoSaving.value = false
  }
}

async function handleToggle(row: HomeConfigModule, enabled: boolean) {
  row.enabled = enabled
  await saveDraft(true)
  ElMessage.success(`${moduleTypeLabel(row.type)} 已${enabled ? '启用' : '停用'}`)
}

const tableRef = ref<any>(null)
let sortableInstance: Sortable | null = null

function initRowDrag() {
  if (sortableInstance) return
  const tbody = tableRef.value?.$el?.querySelector(
    '.el-table__body-wrapper tbody'
  ) as HTMLElement | null
  if (!tbody) return
  sortableInstance = Sortable.create(tbody, {
    handle: '.drag-handle',
    animation: 200,
    ghostClass: 'drag-ghost',
    onEnd: ({ oldIndex, newIndex }) => {
      if (oldIndex === undefined || newIndex === undefined || oldIndex === newIndex) return
      const list = modules.value.slice()
      const [moved] = list.splice(oldIndex, 1)
      list.splice(newIndex, 0, moved)
      modules.value = list.map((m, i) => ({ ...m, sort: i + 1 }))
      saveDraft(true)
    },
  })
}

function openEdit(row: HomeConfigModule) {
  // 深拷贝一份给抽屉编辑
  const idx = modules.value.findIndex(m => m.type === row.type)
  editingModule.value = JSON.parse(JSON.stringify(modules.value[idx]))
  drawerVisible.value = true
}

async function handleDrawerSave(module: HomeConfigModule) {
  // 回写到 modules
  const idx = modules.value.findIndex(m => m.type === module.type)
  if (idx >= 0) {
    modules.value[idx] = module
  }
  drawerVisible.value = false
  await saveDraft()
}

function resetModule(row: HomeConfigModule) {
  // 重置为默认空配置
  const defaults: Record<string, any> = {
    banner: { type: 'banner', enabled: row.enabled, sort: row.sort, items: [] },
    teachers: {
      type: 'teachers',
      enabled: row.enabled,
      sort: row.sort,
      config: { teacher_ids: [] },
    },
    courses: { type: 'courses', enabled: row.enabled, sort: row.sort, config: { course_ids: [] } },
    video: { type: 'video', enabled: row.enabled, sort: row.sort, items: [] },
  }
  const idx = modules.value.findIndex(m => m.type === row.type)
  if (idx >= 0) {
    modules.value[idx] = defaults[row.type]
    saveDraft()
    ElMessage.success('已重置为默认配置')
  }
}

function openPreview() {
  previewVisible.value = true
}

function showPublishConfirm() {
  publishConfirmVisible.value = true
}

async function handlePublish() {
  publishing.value = true
  publishConfirmVisible.value = false
  try {
    // 先保存当前草稿
    await homeConfigApi.updateHomeConfigDraft(buildPayload())
    // 再发布
    const res = await homeConfigApi.publishHomeConfig()
    ElMessage.success(`发布成功！已发布版本 v${res.data?.version || ''}`)
    // 刷新状态
    await fetchDraft()
  } catch (e: any) {
    ElMessage.error(e?.msg || e?.response?.data?.msg || '发布失败')
  } finally {
    publishing.value = false
  }
}

onMounted(async () => {
  await fetchDraft()
  await nextTick()
  initRowDrag()
})
</script>

<style scoped>
.config-card {
  border-radius: 12px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}

.header-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.version-info {
  font-size: 12px;
  color: #909399;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.drag-handle {
  cursor: grab;
  color: #c0c4cc;
  font-size: 18px;
}

.drag-handle:active {
  cursor: grabbing;
}

.module-summary {
  color: #606266;
  font-size: 13px;
}

.module-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.auto-save-tip {
  margin-top: 12px;
  font-size: 12px;
  color: #667eea;
  display: flex;
  align-items: center;
  gap: 4px;
}

.list-error-block {
  padding: 40px 0;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #ebeef5;
}
</style>
