<template>
  <div class="page-container">
    <div class="page-header">
      <h2>会员卡管理</h2>
      <div style="display: flex; gap: 12px">
        <el-button type="primary" @click="openCreateDialog"> 发放会员卡 </el-button>
        <el-button
          type="danger"
          :disabled="selectedCards.length === 0"
          @click="openBatchCancelDialog"
        >
          批量作废
        </el-button>
      </div>
    </div>

    <div style="display: flex; gap: 12px; margin-bottom: 16px; align-items: center">
      <el-input
        v-model="search"
        placeholder="搜索学员或手机号"
        style="width: 240px"
        clearable
        @keyup.enter="handleSearch"
        @clear="handleSearch"
      >
        <template #suffix>
          <el-icon class="search-icon" style="cursor: pointer" @click="handleSearch">
            <Search />
          </el-icon>
        </template>
      </el-input>
      <el-select
        v-model="statusFilter"
        placeholder="状态筛选"
        style="width: 160px"
        clearable
        multiple
        collapse-tags
        collapse-tags-tooltip
        @change="handleSearch"
      >
        <el-option label="未激活" :value="0" />
        <el-option label="正常" :value="1" />
        <el-option label="已过期" :value="2" />
        <el-option label="已冻结" :value="3" />
        <el-option label="已作废" :value="6" />
      </el-select>
    </div>

    <div v-if="loadError" class="list-error-block">
      <el-result icon="error" title="加载会员卡列表失败" :sub-title="loadError">
        <template #extra>
          <el-button type="primary" @click="fetchCards">重试</el-button>
        </template>
      </el-result>
    </div>

    <el-table
      v-else
      v-loading="loading"
      :data="cards"
      stripe
      style="width: 100%"
      empty-text="暂无数据"
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="55" :selectable="checkSelectable" />
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="card_no" label="会员卡号" width="170">
        <template #default="{ row }">
          <el-link
            v-if="row.card_no"
            type="primary"
            :underline="false"
            @click="openDetailDialog(row)"
          >
            {{ row.card_no }}
          </el-link>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="product_name" label="产品名称" min-width="120" />
      <el-table-column prop="card_type" label="计费方式" width="100">
        <template #default="{ row }">
          <el-tag :type="getCardTypeTag(row.card_type)" size="small">
            {{ getCardTypeText(row.card_type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="student_nickname" label="学员" width="100" />
      <el-table-column prop="student_phone" label="手机号" width="120" />
      <el-table-column prop="total_credits" label="总次数" width="80">
        <template #default="{ row }">
          {{ row.card_type === 'count' ? row.total_credits : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="used_credits" label="已用" width="80">
        <template #default="{ row }">
          {{ row.card_type === 'count' ? row.used_credits : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="remaining_credits" label="剩余" width="80">
        <template #default="{ row }">
          {{ row.card_type === 'count' ? row.remaining_credits : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)" size="small">
            {{ getStatusText(row.status) }}
          </el-tag>
          <span
            v-if="isUsedUp(row)"
            style="margin-left: 4px; color: #9e9e9e; font-size: 12px"
            >（已用完）</span
          >
          <!-- 冻结到期但因冲突无法解冻的特殊标记 -->
          <el-tooltip
            v-if="isConflictFrozen(row)"
            content="冻结已到期，但因与同课程类型的其他卡时间冲突，无法自动解冻"
            placement="top"
          >
            <el-icon style="margin-left: 4px; color: #e6a23c; cursor: pointer">
              <WarningFilled />
            </el-icon>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="有效期" width="360">
        <template #default="{ row }">
          {{ formatValidityPeriod(row.valid_from, row.expire_at) }}
        </template>
      </el-table-column>
      <el-table-column v-if="hasFrozenCard" label="冻结信息" width="140">
        <template #default="{ row }">
          <template v-if="row.status === 3">
            <div style="line-height: 1.6">
              <div
                :style="{
                  color: getFrozenRemainingDaysNum(row) <= 0 ? '#e6a23c' : '#67c23a',
                  fontSize: '13px',
                  fontWeight: 500,
                }"
              >
                剩余 {{ getFrozenRemainingDays(row) }} 天解冻
              </div>
              <!-- 冻结到期但因冲突无法解冻的提示 -->
              <div v-if="isConflictFrozen(row)" style="margin-top: 4px">
                <el-tag type="warning" size="small" effect="plain">
                  <el-icon style="margin-right: 4px"><WarningFilled /></el-icon>
                  冻结到期-课程冲突
                </el-tag>
              </div>
            </div>
          </template>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="row.status === 0"
            type="success"
            size="small"
            link
            @click="handleActivate(row)"
          >
            激活
          </el-button>
          <el-button
            v-if="row.status === 1"
            type="warning"
            size="small"
            link
            @click="openFreezeDialog(row)"
          >
            冻结
          </el-button>
          <el-button
            v-if="row.status === 3"
            type="success"
            size="small"
            link
            @click="handleAdminUnfreeze(row)"
          >
            {{ isConflictFrozen(row) ? '强制解冻' : '提前解冻' }}
          </el-button>
          <el-button
            v-if="row.status !== 6 && row.status !== 2"
            type="danger"
            size="small"
            link
            @click="openCancelDialog(row)"
          >
            作废
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrapper">
      <el-pagination
        v-model:current-page="currentPage"
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        @current-change="fetchCards"
      />
    </div>

    <el-dialog
      v-model="dialogVisible"
      title="发放"
      width="560px"
      :close-on-click-modal="false"
      @close="handleDialogClose"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="学员" prop="student_id">
          <el-select
            v-model="form.student_id"
            placeholder="请选择学员"
            filterable
            remote
            :remote-method="handleSearchStudent"
            style="width: 100%"
            @change="handleStudentChange"
          >
            <el-option
              v-for="user in users"
              :key="user.id"
              :label="`${user.nickname || '-'} (${user.phone})`"
              :value="user.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="产品" prop="product_id">
          <el-select
            v-model="form.product_id"
            placeholder="请选择产品"
            style="width: 100%"
            @change="handleProductChange"
          >
            <el-option
              v-for="product in products"
              :key="product.id"
              :label="product.name"
              :value="product.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="selectedProduct?.card_type === 'count'" label="总次数">
          <el-input-number v-model="form.total_credits" :min="1" disabled style="width: 100%" />
          <span style="margin-left: 8px; color: #909399; font-size: 12px">
            次数由产品决定，不可修改
          </span>
        </el-form-item>
        <el-form-item v-if="selectedProduct?.card_type === 'count'" label="有效天数">
          <el-input-number v-model="form.validity_days" :min="1" disabled style="width: 100%" />
          <span style="margin-left: 8px; color: #909399; font-size: 12px">
            天数由产品决定，不可修改
          </span>
        </el-form-item>
        <el-form-item v-if="selectedProduct?.card_type === 'period'" label="有效天数">
          <el-input-number v-model="form.validity_days" :min="1" disabled style="width: 100%" />
          <span style="margin-left: 8px; color: #909399; font-size: 12px">
            天数由产品决定，不可修改
          </span>
        </el-form-item>
        <el-form-item v-if="selectedProduct?.card_type === 'unlimited'" label="计费方式">
          <el-tag type="success"> 无限卡 </el-tag>
          <span style="margin-left: 8px; color: #909399; font-size: 12px">
            无限卡无次数和天数限制
          </span>
        </el-form-item>
        <el-form-item label="生效时间" prop="valid_from">
          <el-date-picker
            v-model="form.valid_from"
            type="date"
            placeholder="选择生效日期（留空表示立即激活）"
            style="width: 100%"
            clearable
            :disabled-date="disabledDate"
            value-format="YYYY-MM-DD"
          />
          <div v-if="minValidDate" style="margin-top: 4px; color: #e6a23c; font-size: 12px">
            因学员已有有效卡，最早可选日期：<strong>{{ minValidDate }}</strong>
          </div>
          <div v-else style="margin-top: 4px; color: #909399; font-size: 12px">
            选择日期后，生效时间将为当天的 00:00:00，到期时间为有效期最后一天的 23:59:59
          </div>
        </el-form-item>
        <el-form-item label="备注" prop="remark">
          <el-input v-model="form.remark" type="textarea" :rows="3" placeholder="请输入备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false"> 取消 </el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit"> 确定 </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailDialogVisible" title="详情" width="600px">
      <el-descriptions v-if="detailCard" :column="2" border>
        <el-descriptions-item label="会员卡号" :span="2">
          {{ detailCard.card_no || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="产品名称">
          {{ detailCard.product_name || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="计费方式">
          {{ getCardTypeText(detailCard.card_type) }}
        </el-descriptions-item>
        <el-descriptions-item label="学员">
          {{ detailCard.student_nickname || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="手机号">
          {{ detailCard.student_phone || '-' }}
        </el-descriptions-item>
        <template v-if="detailCard.card_type === 'count'">
          <el-descriptions-item label="总次数">
            {{ detailCard.total_credits ?? '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="已用次数">
            {{ detailCard.used_credits ?? 0 }}
          </el-descriptions-item>
          <el-descriptions-item label="剩余次数">
            {{ detailCard.remaining_credits ?? '-' }}
          </el-descriptions-item>
        </template>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(detailCard.status)" size="small">
            {{ getStatusText(detailCard.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="有效期" :span="2">
          {{ formatValidityPeriod(detailCard.valid_from, detailCard.expire_at) }}
        </el-descriptions-item>
        <template v-if="detailCard.status === 3">
          <el-descriptions-item label="冻结时间">
            {{ detailCard.frozen_at ? formatDateTime(detailCard.frozen_at) : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="冻结到期">
            {{ detailCard.frozen_until ? formatFrozenUntil(detailCard.frozen_until) : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="剩余冻结天数" :span="2">
            <span style="color: #e6a23c; font-weight: 600">
              {{ getFrozenRemainingDays(detailCard) }} 天
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="冻结原因" :span="2">
            {{ detailCard.frozen_reason || '-' }}
          </el-descriptions-item>
        </template>
        <el-descriptions-item v-else label="冻结原因" :span="2">
          {{ detailCard.frozen_reason || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">
          {{ detailCard.created_at ? formatDateTime(detailCard.created_at) : '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="更新时间" :span="2">
          {{ detailCard.updated_at ? formatDateTime(detailCard.updated_at) : '-' }}
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <el-dialog
      v-model="freezeDialogVisible"
      title="冻结"
      width="460px"
      :close-on-click-modal="false"
    >
      <el-form ref="freezeFormRef" :model="freezeForm" :rules="freezeRules" label-width="100px">
        <el-form-item label="冻结天数" prop="freeze_days">
          <el-input-number
            v-model="freezeForm.freeze_days"
            :min="1"
            :max="365"
            style="width: 100%"
          />
          <span style="margin-left: 8px; color: #909399; font-size: 12px">1-365天</span>
        </el-form-item>
        <el-form-item label="冻结原因" prop="reason">
          <el-input
            v-model="freezeForm.reason"
            type="textarea"
            :rows="3"
            placeholder="请输入冻结原因"
          />
        </el-form-item>
      </el-form>
      <!-- F6.7 影响面区域（四态；查询失败不阻断主操作） -->
      <div class="affected-section">
        <el-skeleton v-if="affectedLoading" :rows="2" animated />
        <div v-else-if="affectedError" class="affected-error">
          <span>影响面查询失败，可重试或继续操作</span>
          <el-button link type="primary" size="small" @click="retryLoadAffected"> 重试 </el-button>
        </div>
        <template v-else-if="affectedData">
          <el-alert
            v-if="affectedData.total > 0"
            type="warning"
            show-icon
            :closable="false"
            :title="`该卡有 ${affectedData.total} 个有效预约，冻结后学员可自助换卡或联系机构处理`"
          />
          <div v-else class="affected-empty">该卡无受影响预约</div>
          <ul v-if="affectedData.total > 0" class="affected-list">
            <li v-for="item in affectedData.items" :key="item.booking_id">
              <span class="affected-course">{{ item.course_name || '未知课程' }}</span>
              <span class="affected-time">{{ formatDateTime(item.start_at) }}</span>
              <el-tag size="small" :type="item.status === 3 ? 'warning' : 'primary'">
                {{ item.status === 3 ? '已签到' : '已预约' }}
              </el-tag>
            </li>
          </ul>
          <div v-if="affectedData.total > 0" class="affected-hint">
            以上为实时查询结果，仅预览前 {{ affectedData.items.length }} 条，以操作时实际为准
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="freezeDialogVisible = false"> 取消 </el-button>
        <el-button type="primary" :loading="submitting" @click="handleFreeze"> 确定 </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="cancelDialogVisible"
      title="作废"
      width="460px"
      :close-on-click-modal="false"
    >
      <el-form ref="cancelFormRef" :model="cancelForm" :rules="cancelRules" label-width="100px">
        <el-form-item label="作废原因" prop="reason">
          <el-input
            v-model="cancelForm.reason"
            type="textarea"
            :rows="3"
            placeholder="请输入作废原因"
          />
        </el-form-item>
      </el-form>
      <!-- F6.7 影响面区域（四态；查询失败不阻断主操作） -->
      <div class="affected-section">
        <el-skeleton v-if="affectedLoading" :rows="2" animated />
        <div v-else-if="affectedError" class="affected-error">
          <span>影响面查询失败，可重试或继续操作</span>
          <el-button link type="primary" size="small" @click="retryLoadAffected"> 重试 </el-button>
        </div>
        <template v-else-if="affectedData">
          <el-alert
            v-if="affectedData.total > 0"
            type="danger"
            show-icon
            :closable="false"
            :title="`该卡有 ${affectedData.total} 个有效预约。作废后卡不可恢复，这些预约需学员换卡或机构人工处理。`"
          />
          <div v-else class="affected-empty">该卡无受影响预约</div>
          <ul v-if="affectedData.total > 0" class="affected-list">
            <li v-for="item in affectedData.items" :key="item.booking_id">
              <span class="affected-course">{{ item.course_name || '未知课程' }}</span>
              <span class="affected-time">{{ formatDateTime(item.start_at) }}</span>
              <el-tag size="small" :type="item.status === 3 ? 'warning' : 'primary'">
                {{ item.status === 3 ? '已签到' : '已预约' }}
              </el-tag>
            </li>
          </ul>
          <div v-if="affectedData.total > 0" class="affected-hint">
            以上为实时查询结果，仅预览前 {{ affectedData.items.length }} 条，以操作时实际为准
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="cancelDialogVisible = false"> 取消 </el-button>
        <el-button
          type="danger"
          :loading="submitting"
          @click="handleCancel"
        >
          {{ affectedData && affectedData.total > 0 ? '确定作废' : '确定' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 批量作废对话框 -->
    <el-dialog
      v-model="batchCancelDialogVisible"
      title="批量"
      width="500px"
      :close-on-click-modal="false"
    >
      <div class="batch-cancel-info">
        <p>
          已选择 <strong>{{ selectedCards.length }}</strong> 张会员卡进行批量作废
        </p>
        <div class="selected-cards-list">
          <div v-for="card in selectedCards" :key="card.id" class="selected-card-item">
            <span>{{ card.student_nickname || '-' }}</span>
            <span>{{ card.student_phone || '-' }}</span>
            <el-tag :type="getStatusType(card.status)" size="small">
              {{ getStatusText(card.status) }}
            </el-tag>
          </div>
        </div>
      </div>
      <el-form
        ref="batchCancelFormRef"
        :model="batchCancelForm"
        :rules="batchCancelRules"
        label-width="90px"
        style="margin-top: 16px"
      >
        <el-form-item label="作废原因" prop="reason">
          <el-input
            v-model="batchCancelForm.reason"
            type="textarea"
            :rows="3"
            placeholder="请输入批量作废原因"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchCancelDialogVisible = false"> 取消 </el-button>
        <el-button type="primary" :loading="submitting" @click="handleBatchCancel">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 续卡提示对话框 -->
    <el-dialog
      v-model="renewalDialogVisible"
      title=""
      width="480px"
      :show-close="true"
      :close-on-click-modal="false"
      custom-class="renewal-dialog"
    >
      <div class="renewal-content">
        <div class="renewal-header">
          <span class="renewal-icon">️</span>
          <span class="renewal-title">该学员已有 {{ renewalCardCount }} 张同课程类型有效卡</span>
        </div>
        <div class="renewal-subtitle">如需继续发卡（续卡），请确认以下规则：</div>
        <div class="renewal-rules">
          <div class="rules-title">续卡规则</div>
          <div class="rules-item">• 新卡生效时间必须晚于旧卡到期时间的次日</div>
          <div v-if="renewalEarliestDate" class="rules-hint">
            ✅ 系统已自动设置最早生效日期：<strong>{{ renewalEarliestDate }}</strong>
          </div>
        </div>
        <div class="renewal-footer">请确认生效时间后，重新点击"确定"按钮</div>
      </div>
    </el-dialog>

    <!-- 冲突处理对话框 -->
    <el-dialog
      v-model="conflictDialogVisible"
      title="⚠️ 冻结到期-课程冲突"
      width="600px"
      :close-on-click-modal="false"
    >
      <div class="conflict-dialog-content">
        <!-- 卡信息 -->
        <div class="card-info">
          <div class="info-row">
            <span class="label">产品名称：</span>
            <span class="value product-name">{{ conflictCard?.product_name || '会员卡' }}</span>
          </div>
          <div class="info-row">
            <span class="label">会员卡号：</span>
            <span class="value card-no">{{ conflictCard?.card_no || '-' }}</span>
          </div>
          <div class="info-row">
            <span class="label">冻结到期：</span>
            <span class="value">{{
              conflictCard?.frozen_until ? formatFrozenUntil(conflictCard.frozen_until) : '-'
            }}</span>
          </div>
        </div>

        <!-- 冲突卡列表 -->
        <div v-if="conflictCardsList.length > 0" class="conflict-section">
          <div class="section-title">
            <el-icon style="color: #e6a23c; margin-right: 4px"><WarningFilled /></el-icon>
            检测到以下冲突卡：
          </div>
          <div class="conflict-cards-list">
            <div v-for="item in conflictCardsList" :key="item.id" class="conflict-card-item">
              <div class="conflict-card-info">
                <div class="card-name-row">
                  <span class="card-product-name">{{ item.product_name || '会员卡' }}</span>
                  <span class="card-no-badge">#{{ item.card_no }}</span>
                </div>
                <div class="card-details">
                  <span>状态：{{ getStatusText(item.status) }}</span>
                  <span v-if="item.card_type === 'count'"
                    >| 剩余：{{ item.remaining_credits }}次</span
                  >
                  <span>| 有效期：{{ formatValidityPeriod(item.valid_from, item.expire_at) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 处理方式选择 -->
        <div class="action-section">
          <div class="section-title">请选择处理方式：</div>
          <el-radio-group v-model="selectedAction" class="action-radio-group">
            <el-radio label="unfreeze_and_cancel">
              解冻并作废冲突卡（冲突卡剩余次数清零）
            </el-radio>
            <el-radio label="unfreeze_and_freeze"> 解冻并冻结冲突卡（冲突卡冻结365天） </el-radio>
          </el-radio-group>
        </div>

        <!-- 备注 -->
        <div class="remark-section">
          <el-input
            v-model="conflictRemark"
            type="textarea"
            placeholder="请输入操作备注（可选）"
            :rows="2"
          />
        </div>
      </div>

      <template #footer>
        <el-button @click="conflictDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleConfirmConflictAction">
          确认
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import {
  cardTypeApi,
  type MembershipCard,
  membershipCardApi,
  type MembershipCardCreateParams,
  type MembershipCardProduct,
  userApi,
} from '@dance-saas/api-client'
import { Search, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

// F6.7：受影响预约响应类型由 api-client 方法签名推导（单一事实源为 api-client，不在本地重复定义 DTO）
type AffectedBookingsData = Awaited<
  ReturnType<typeof membershipCardApi.getAffectedBookings>
>['data']

const loading = ref(false)
const loadError = ref('')
const submitting = ref(false)
const cards = ref<MembershipCard[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const search = ref('')
const statusFilter = ref<number[]>([])
const users = ref<any[]>([])
const products = ref<MembershipCardProduct[]>([])

const hasFrozenCard = computed(() => cards.value.some(c => c.status === 3))

const dialogVisible = ref(false)
const formRef = ref()
const selectedProduct = ref<any>(null)
const minValidDate = ref<string | null>(null)

const form = ref<MembershipCardCreateParams>({
  student_id: undefined,
  product_id: undefined,
  total_credits: undefined,
  validity_days: undefined,
  valid_from: undefined,
  allow_duplicate: false,
  remark: '',
})

const rules = {
  student_id: [{ required: true, message: '请选择学员', trigger: 'change' }],
  product_id: [{ required: true, message: '请选择产品', trigger: 'change' }],
}

const freezeDialogVisible = ref(false)
const freezeFormRef = ref()
const freezeForm = ref({ reason: '', freeze_days: 7 })
const freezingCardId = ref<number | null>(null)

const freezeRules = {
  freeze_days: [{ required: true, message: '请输入冻结天数', trigger: 'blur' }],
  reason: [{ required: true, message: '请输入冻结原因', trigger: 'blur' }],
}

const cancelDialogVisible = ref(false)
const cancelFormRef = ref()
const cancelForm = ref({ reason: '' })
const cancelingCardId = ref<number | null>(null)

const cancelRules = {
  reason: [{ required: true, message: '请输入作废原因', trigger: 'blur' }],
}

const batchCancelDialogVisible = ref(false)
const batchCancelFormRef = ref()
const batchCancelForm = ref({ reason: '' })
const selectedCards = ref<MembershipCard[]>([])

const batchCancelRules = {
  reason: [{ required: true, message: '请输入作废原因', trigger: 'blur' }],
}

const renewalDialogVisible = ref(false)
const renewalCardCount = ref('')
const renewalEarliestDate = ref<string | null>(null)

// 冲突处理相关
const conflictDialogVisible = ref(false)
const conflictCard = ref<MembershipCard | null>(null)
const conflictCardsList = ref<any[]>([])
const selectedAction = ref('unfreeze_and_cancel')
const conflictRemark = ref('')

const detailDialogVisible = ref(false)
const detailCard = ref<MembershipCard | null>(null)

// F6.7 影响面查询状态（冻结/作废弹窗共用，同一时间仅一个弹窗打开）
const affectedLoading = ref(false)
const affectedError = ref('')
const affectedData = ref<AffectedBookingsData | null>(null)
const affectedCardId = ref<number | null>(null)
// 请求序号，防止快速切换弹窗时旧响应覆盖新状态
let affectedReqSeq = 0

function resetAffectedState(cardId: number) {
  affectedCardId.value = cardId
  affectedData.value = null
  affectedError.value = ''
  affectedLoading.value = false
}

async function loadAffectedBookings(cardId: number) {
  const seq = ++affectedReqSeq
  affectedLoading.value = true
  affectedError.value = ''
  try {
    const res = await membershipCardApi.getAffectedBookings(cardId, { page: 1, page_size: 5 })
    if (seq !== affectedReqSeq) return
    affectedData.value = res.data
  } catch (e: any) {
    if (seq !== affectedReqSeq) return
    affectedData.value = null
    affectedError.value = e?.response?.data?.msg || '影响面查询失败'
  } finally {
    if (seq === affectedReqSeq) {
      affectedLoading.value = false
    }
  }
}

function retryLoadAffected() {
  if (affectedCardId.value != null) {
    loadAffectedBookings(affectedCardId.value)
  }
}

async function fetchCards() {
  loading.value = true
  loadError.value = ''
  try {
    const params: any = {
      page: currentPage.value,
      page_size: pageSize.value,
    }
    if (statusFilter.value && statusFilter.value.length > 0) {
      params.status = statusFilter.value.join(',')
    }
    if (search.value) {
      params.keyword = search.value
    }
    const res = await membershipCardApi.list(params)
    cards.value = res.data.items
    total.value = res.data.total
  } catch (e: any) {
    loadError.value = e?.response?.data?.msg || '加载会员卡列表失败'
    ElMessage.error(loadError.value)
  } finally {
    loading.value = false
  }
}

async function fetchUsers(keyword?: string) {
  try {
    const params: any = { page: 1, page_size: 100, role_code: 'student' }
    if (keyword) {
      params.keyword = keyword
    }
    const res = await userApi.list(params)
    // API client 已解包，res.data 就是 { items: [...], total: ... }
    users.value = res.data?.items || []
    console.log('✅ 学员列表加载成功，数量:', users.value.length)
  } catch (e: any) {
    console.error('❌ 加载学员列表失败', e)
    ElMessage.error('加载学员列表失败')
  }
}

async function fetchProducts() {
  try {
    const res = await cardTypeApi.list({ page: 1, page_size: 100, status: 1 })
    products.value = res.data.items
    console.log('✅ 已上架产品列表加载成功，数量:', products.value.length)
    console.log('📦 产品数据示例:', products.value[0])
  } catch (e: any) {
    console.error(' 加载产品列表失败', e)
  }
}

function handleSearch() {
  currentPage.value = 1
  fetchCards()
}

function handleSearchStudent(keyword: string) {
  fetchUsers(keyword)
}

function disabledDate(time: Date) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  // 如果有最早生效日期限制，则禁用该日期之前的所有日期
  if (minValidDate.value) {
    const minDate = new Date(minValidDate.value)
    minDate.setHours(0, 0, 0, 0)
    return time.getTime() < minDate.getTime()
  }

  // 否则只允许选择今天及之后的日期
  return time.getTime() < today.getTime()
}

function openCreateDialog() {
  minValidDate.value = null
  form.value = {
    student_id: undefined,
    product_id: undefined,
    total_credits: undefined,
    validity_days: undefined,
    valid_from: undefined,
    allow_duplicate: false,
    remark: '',
  }
  users.value = []
  dialogVisible.value = true
  formRef.value?.clearValidate()
  // 打开弹窗时才加载学员列表
  fetchUsers()
}

function handleStudentChange() {
  // 清空之前设置的生效时间
  form.value.valid_from = undefined
  // 清空最早可选日期限制
  minValidDate.value = null
  // 重置 allow_duplicate 标志
  form.value.allow_duplicate = false
}

function handleProductChange(productId: number) {
  const product = products.value.find(p => p.id === productId)
  if (!product) return

  selectedProduct.value = product
  console.log(
    '📦 选择产品:',
    product.name,
    '次数:',
    product.total_credits,
    '天数:',
    product.validity_days
  )

  // 自动带入产品信息
  form.value.total_credits = product.total_credits ?? undefined
  form.value.validity_days = product.validity_days ?? undefined

  console.log(
    '✅ 表单已更新 - 总次数:',
    form.value.total_credits,
    '有效天数:',
    form.value.validity_days
  )
}

function openDetailDialog(row: MembershipCard) {
  detailCard.value = row
  detailDialogVisible.value = true
}

function handleDialogClose() {
  formRef.value?.clearValidate()
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const payload: any = { ...form.value }
    // 移除 undefined 值
    Object.keys(payload).forEach(key => {
      if (payload[key] === undefined) {
        delete payload[key]
      }
    })
    // valid_from 已经是 YYYY-MM-DD 格式，不需要转换
    // 后端会自动将其转为 datetime 并设置时分秒为 00:00:00
    console.log('📤 发送请求数据:', payload)
    await membershipCardApi.create(payload)
    ElMessage.success('会员卡发放成功')
    dialogVisible.value = false
    fetchCards()
  } catch (e: any) {
    console.error('❌ 发放会员卡失败:', e)
    console.error('  请求数据:', e?.config?.data)
    console.error('  响应数据:', e?.response?.data)

    const status = e?.response?.status
    // 兼容后端返回的 detail 和 msg 字段
    const errorMsg = e?.response?.data?.detail || e?.response?.data?.msg || '操作失败'

    // 根据不同状态码给出详细提示
    if (status === 409) {
      // 重复发卡冲突 - 提示用户修改生效时间后重新提交
      const match = errorMsg.match(/(\d{4}-\d{2}-\d{2})/)
      const earliestDate = match ? match[1] : null

      // 提取已有卡数量（如果有）
      const countMatch = errorMsg.match(/(\d+)\s*张/)
      const cardCount = countMatch ? countMatch[1] : ''

      // 设置续卡对话框数据
      renewalCardCount.value = cardCount
      renewalEarliestDate.value = earliestDate
      renewalDialogVisible.value = true

      // 设置 allow_duplicate=true，允许用户重新提交（用户无需感知此参数）
      form.value.allow_duplicate = true

      // 如果后端返回了最早生效日期，自动设置到表单中并禁用之前的日期
      if (earliestDate) {
        minValidDate.value = earliestDate
        form.value.valid_from = earliestDate
      }

      // 不关闭对话框，让用户修改后重新提交
      submitting.value = false
      return
    } else if (status === 403) {
      // 权限错误
      ElMessage.error(`❌ 权限不足：${errorMsg}\n\n请联系管理员确认您的操作权限。`)
    } else if (status === 400) {
      // 业务参数错误
      ElMessage.error(`❌ 参数错误：${errorMsg}`)
    } else if (status === 404) {
      // 资源不存在
      ElMessage.error(`❌ 资源不存在：${errorMsg}`)
    } else if (status === 500) {
      // 服务器错误
      ElMessage.error('❌ 服务器内部错误，请联系技术人员处理。')
    } else {
      // 其他错误
      ElMessage.error(`❌ 操作失败（HTTP ${status}）：${errorMsg}`)
    }
  } finally {
    submitting.value = false
  }
}

async function handleActivate(row: MembershipCard) {
  try {
    await ElMessageBox.confirm(`确定要激活会员卡「${row.product_name || '-'}」吗？`, '提示', {
      type: 'warning',
    })
    await membershipCardApi.adminActivate(row.id)
    ElMessage.success('激活成功')
    fetchCards()
  } catch (e: any) {
    if (e !== 'cancel') {
      const status = e?.response?.status
      const errorMsg = e?.response?.data?.detail || e?.response?.data?.msg || '激活失败'

      if (status === 409) {
        // 重复卡冲突 - 给出明确的操作指引
        ElMessage({
          message: `${errorMsg}`,
          type: 'warning',
          duration: 5000,
          showClose: true,
        })
      } else {
        ElMessage.error(`❌ ${errorMsg}`)
      }
    }
  }
}

function openFreezeDialog(row: MembershipCard) {
  freezingCardId.value = row.id
  freezeForm.value = { reason: '', freeze_days: 7 }
  freezeDialogVisible.value = true
  freezeFormRef.value?.clearValidate()
  // F6.7：打开弹窗即查影响面，失败不阻断冻结操作（R-7）
  resetAffectedState(row.id)
  loadAffectedBookings(row.id)
}

async function handleFreeze() {
  const valid = await freezeFormRef.value?.validate().catch(() => false)
  if (!valid || !freezingCardId.value) return

  submitting.value = true
  try {
    await membershipCardApi.freeze(freezingCardId.value, {
      reason: freezeForm.value.reason,
      freeze_days: freezeForm.value.freeze_days,
    })
    ElMessage.success('冻结成功')
    freezeDialogVisible.value = false
    fetchCards()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '冻结失败')
  } finally {
    submitting.value = false
  }
}

// 管理员解冻（带冲突检查）
async function handleAdminUnfreeze(row: MembershipCard) {
  try {
    // 先检查冲突
    const res = await membershipCardApi.checkConflict(row.id)
    const conflictData = res.data

    if (conflictData?.has_conflict) {
      // 有冲突，显示冲突处理对话框
      conflictCard.value = row
      conflictCardsList.value = conflictData.conflict_cards || []
      selectedAction.value = 'unfreeze_and_cancel'
      conflictRemark.value = ''
      conflictDialogVisible.value = true
    } else {
      // 无冲突，直接解冻
      await ElMessageBox.confirm(
        `确定要提前解冻学员「${row.student_nickname || '未知'}」的会员卡吗？解冻后卡片将立即恢复正常使用。`,
        '提前解冻确认',
        {
          confirmButtonText: '确定解冻',
          cancelButtonText: '取消',
          type: 'warning',
        }
      )
      await membershipCardApi.unfreeze(row.id)
      ElMessage.success('解冻成功')
      fetchCards()
    }
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.response?.data?.msg || '解冻失败')
    }
  }
}

// 确认执行冲突处理操作
async function handleConfirmConflictAction() {
  if (!conflictCard.value) return

  submitting.value = true
  try {
    const payload: any = {
      action: selectedAction.value,
      remark: conflictRemark.value,
      conflict_card_ids: conflictCardsList.value.map(c => c.id),
    }

    await membershipCardApi.unfreezeWithConflict(conflictCard.value.id, payload)
    ElMessage.success('操作成功')
    conflictDialogVisible.value = false
    fetchCards()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '操作失败')
  } finally {
    submitting.value = false
  }
}

function openCancelDialog(row: MembershipCard) {
  cancelingCardId.value = row.id
  cancelForm.value = { reason: '' }
  cancelDialogVisible.value = true
  cancelFormRef.value?.clearValidate()
  // F6.7：打开弹窗即查影响面，失败不阻断作废操作（R-7）
  resetAffectedState(row.id)
  loadAffectedBookings(row.id)
}

async function handleCancel() {
  if (!cancelFormRef.value) return

  try {
    await cancelFormRef.value.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    await membershipCardApi.cancel(cancelingCardId.value!, { reason: cancelForm.value.reason })
    ElMessage.success('作废成功')
    cancelDialogVisible.value = false
    fetchCards()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '作废失败')
  } finally {
    submitting.value = false
  }
}

function checkSelectable(row: MembershipCard) {
  // 已过期(status=2)和已作废(status=6)的卡不可选择进行批量作废
  return row.status !== 2 && row.status !== 6
}

function handleSelectionChange(selection: MembershipCard[]) {
  selectedCards.value = selection
}

function openBatchCancelDialog() {
  if (selectedCards.value.length === 0) {
    ElMessage.warning('请先选择要作废的会员卡')
    return
  }
  batchCancelForm.value = { reason: '' }
  batchCancelDialogVisible.value = true
  batchCancelFormRef.value?.clearValidate()
}

async function handleBatchCancel() {
  if (!batchCancelFormRef.value) return

  try {
    await batchCancelFormRef.value.validate()
  } catch {
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要批量作废选中的 ${selectedCards.value.length} 张会员卡吗？此操作不可撤销。`,
      '批量作废确认',
      {
        confirmButtonText: '确定作废',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch {
    return
  }

  submitting.value = true
  try {
    const cardIds = selectedCards.value.map(card => card.id)
    await membershipCardApi.batchCancel(cardIds, { reason: batchCancelForm.value.reason })
    ElMessage.success(`成功作废 ${cardIds.length} 张会员卡`)
    batchCancelDialogVisible.value = false
    selectedCards.value = []
    fetchCards()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.msg || '批量作废失败')
  } finally {
    submitting.value = false
  }
}

function getStatusType(status: number) {
  const map: Record<number, string> = {
    0: 'info', // 未激活
    1: 'success', // 正常
    2: 'warning', // 已过期
    3: 'danger', // 已冻结
    6: 'info', // 已作废
  }
  return map[status] || 'info'
}

function getStatusText(status: number) {
  const map: Record<number, string> = {
    0: '未激活',
    1: '正常',
    2: '已过期',
    3: '已冻结',
    6: '已作废',
  }
  return map[status] || '未知'
}

function getCardTypeText(type: string) {
  const map: Record<string, string> = { count: '次卡', period: '期卡', unlimited: '无限卡' }
  return map[type] || type
}

const cardTypeTagMap: Record<string, string> = {
  count: 'primary',
  period: 'success',
  unlimited: 'warning',
}

function getCardTypeTag(type: string) {
  return cardTypeTagMap[type] || 'info'
}

// 格式化时间为 yyyy-MM-dd HH:mm:ss
function formatDateTime(dateStr: string) {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}

// 格式化冻结到期时间（日期部分 + 23:59:59）
function formatFrozenUntil(dateStr: string) {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day} 23:59:59`
}

// 格式化有效期时间（开始时间 00:00:00，结束时间 23:59:59）
function formatValidityPeriod(startDate: string | null, endDate: string | null) {
  if (!startDate || !endDate) return '-'
  const start = new Date(startDate)
  const end = new Date(endDate)

  const startYear = start.getFullYear()
  const startMonth = String(start.getMonth() + 1).padStart(2, '0')
  const startDay = String(start.getDate()).padStart(2, '0')

  const endYear = end.getFullYear()
  const endMonth = String(end.getMonth() + 1).padStart(2, '0')
  const endDay = String(end.getDate()).padStart(2, '0')

  return `${startYear}-${startMonth}-${startDay} 00:00:00 ~ ${endYear}-${endMonth}-${endDay} 23:59:59`
}

function getFrozenRemainingDays(card: MembershipCard): number | string {
  if (!card.frozen_until) return '-'
  const frozenUntil = new Date(card.frozen_until).getTime()
  const now = Date.now()
  const diffMs = frozenUntil - now
  if (diffMs <= 0) return 0
  // 使用 Math.floor 计算完整天数，避免将几小时向上取整为一天
  return Math.floor(diffMs / (1000 * 60 * 60 * 24))
}

// 获取冻结剩余天数（仅返回数字，用于模板比较）
function getFrozenRemainingDaysNum(card: MembershipCard): number {
  if (!card.frozen_until) return 999
  const frozenUntil = new Date(card.frozen_until).getTime()
  const now = Date.now()
  const diffMs = frozenUntil - now
  if (diffMs <= 0) return 0
  return Math.floor(diffMs / (1000 * 60 * 60 * 24))
}

// 判断冻结卡是否因冲突无法解冻
function isConflictFrozen(card: MembershipCard) {
  // 冻结已到期（frozen_until 已过）但仍有冲突
  if (card.status !== 3 || !card.frozen_until) return false
  const frozenUntil = new Date(card.frozen_until).getTime()
  const now = Date.now()
  return frozenUntil <= now && (card as any).has_conflict === true
}

// 判断次卡是否已用完（ACTIVE + count + remaining_credits === 0）
function isUsedUp(card: MembershipCard): boolean {
  return (
    card.status === 1 &&
    card.card_type === 'count' &&
    (card.remaining_credits ?? 0) === 0
  )
}

onMounted(() => {
  fetchCards()
  fetchProducts()
})
</script>

<style scoped>
/* 会员卡号可点击样式 */
:deep(.el-link.is-underline) {
  font-weight: 500;
}

.list-error-block {
  padding: 40px 0;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #ebeef5;
}

/* F6.7 影响面区域 */
.affected-section {
  margin-top: 4px;
  padding-top: 12px;
  border-top: 1px dashed #ebeef5;
}

.affected-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
  color: #e6a23c;
}

.affected-empty {
  font-size: 13px;
  color: #909399;
}

.affected-list {
  margin: 10px 0 0;
  padding: 0;
  list-style: none;
  max-height: 180px;
  overflow-y: auto;
}

.affected-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 13px;
  color: #606266;
  border-bottom: 1px solid #f5f7fa;
}

.affected-list li:last-child {
  border-bottom: none;
}

.affected-course {
  font-weight: 500;
  color: #303133;
}

.affected-time {
  flex: 1;
  color: #909399;
  font-size: 12px;
}

.affected-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}

/* 续卡提示对话框样式 */
:deep(.renewal-dialog) {
  border-radius: 12px;
  overflow: hidden;
}

:deep(.renewal-dialog .el-dialog__header) {
  padding: 0;
  margin: 0;
}

:deep(.renewal-dialog .el-dialog__headerbtn) {
  top: 12px;
  right: 12px;
  font-size: 18px;
}

.renewal-content {
  padding: 4px 0;
}

.renewal-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.renewal-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.renewal-title {
  font-size: 14px;
  font-weight: 600;
  color: #e6a23c;
}

.renewal-subtitle {
  font-size: 13px;
  color: #606266;
  margin-bottom: 12px;
}

.renewal-rules {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 12px;
}

.rules-title {
  font-size: 13px;
  color: #e6a23c;
  font-weight: 500;
  margin-bottom: 8px;
}

.rules-item {
  font-size: 12px;
  color: #606266;
}

.rules-hint {
  font-size: 12px;
  color: #67c23a;
  margin-top: 6px;
}

.renewal-footer {
  font-size: 12px;
  color: #909399;
}

.batch-cancel-info {
  margin-bottom: 16px;

  p {
    margin: 0 0 12px;
    font-size: 14px;
    color: #606266;

    strong {
      color: #f56c6c;
      font-size: 16px;
    }
  }
}

.selected-cards-list {
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 8px;
  background: #fafafa;

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

.selected-card-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  margin-bottom: 4px;
  background: #fff;
  border-radius: 4px;
  font-size: 13px;
  color: #606266;

  &:last-child {
    margin-bottom: 0;
  }

  span:first-child {
    font-weight: 500;
    min-width: 60px;
  }

  span:nth-child(2) {
    color: #909399;
    min-width: 100px;
  }
}

/* 冲突处理对话框样式 */
.conflict-dialog-content {
  .card-info {
    background: #f5f7fa;
    padding: 16px;
    border-radius: 8px;
    margin-bottom: 20px;

    .info-row {
      display: flex;
      align-items: center;
      margin-bottom: 8px;
      font-size: 14px;

      &:last-child {
        margin-bottom: 0;
      }

      .label {
        color: #909399;
        min-width: 80px;
        flex-shrink: 0;
      }

      .value {
        color: #303133;
        font-weight: 500;

        &.product-name {
          font-size: 15px;
          font-weight: 600;
          color: #1d2129;
        }

        &.card-no {
          display: inline-flex;
          align-items: center;
          padding: 4px 12px;
          background: #e8f3ff;
          color: #165dff;
          font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
          font-size: 14px;
          font-weight: 600;
          border-radius: 6px;
          letter-spacing: 0.5px;
        }
      }
    }
  }

  .conflict-section {
    margin-bottom: 20px;

    .section-title {
      display: flex;
      align-items: center;
      font-size: 14px;
      font-weight: 600;
      color: #303133;
      margin-bottom: 12px;
    }

    .conflict-cards-list {
      max-height: 200px;
      overflow-y: auto;
      border: 1px solid #ebeef5;
      border-radius: 8px;
      padding: 8px;
      background: #fafafa;

      &::-webkit-scrollbar {
        width: 4px;
      }

      &::-webkit-scrollbar-track {
        background: transparent;
      }

      &::-webkit-scrollbar-thumb {
        background: #dcdfe6;
        border-radius: 2px;
      }

      .conflict-card-item {
        padding: 16px 20px;
        margin-bottom: 12px;
        background: #fff;
        border-radius: 8px;
        border: 1px solid #ebeef5;

        &:last-child {
          margin-bottom: 0;
        }

        .conflict-card-info {
          .card-name-row {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 10px;

            .card-product-name {
              font-size: 15px;
              font-weight: 500;
              color: #303133;
            }

            .card-no-badge {
              display: inline-flex;
              align-items: center;
              padding: 4px 12px;
              background: #e8f3ff;
              color: #165dff;
              font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
              font-size: 13px;
              font-weight: 600;
              border-radius: 4px;
              letter-spacing: 0.5px;
            }
          }

          .card-details {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            font-size: 13px;
            color: #909399;
            line-height: 1.8;

            span {
              white-space: nowrap;
            }
          }
        }
      }
    }
  }

  .action-section {
    margin-bottom: 16px;

    .section-title {
      font-size: 14px;
      font-weight: 600;
      color: #303133;
      margin-bottom: 12px;
    }

    .action-radio-group {
      display: flex;
      flex-direction: column;
      gap: 12px;
      align-items: flex-start;

      :deep(.el-radio) {
        margin-right: 0;
        margin-left: 0;
        font-size: 14px;
        color: #606266;
        justify-content: flex-start;
        width: 100%;
      }

      :deep(.el-radio__input) {
        margin-right: 8px;
        flex-shrink: 0;
      }

      :deep(.el-radio__label) {
        white-space: normal;
      }
    }
  }

  .remark-section {
    :deep(.el-textarea__inner) {
      font-size: 14px;
    }
  }
}
</style>
