<template>
  <div class="page-container">
    <div class="page-header">
      <h2>机构设置</h2>
    </div>

    <el-card shadow="never" style="max-width:640px">
      <el-form label-width="100px" label-position="left">
        <el-form-item label="机构名称">
          <el-input value="舞蹈培训机构" />
        </el-form-item>
        <el-form-item label="机构标识">
          <el-input value="dance-school" disabled />
          <div style="font-size:12px;color:#909399;margin-top:4px">机构标识不可修改，用于登录和 API 访问</div>
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input value="010-12345678" />
        </el-form-item>
        <el-form-item label="联系地址">
          <el-input value="北京市朝阳区舞蹈大厦 10 层" />
        </el-form-item>
        <el-form-item label="营业时间">
          <el-time-picker v-model="bizHours" is-range range-separator="至" start-placeholder="开始" end-placeholder="结束" value-format="HH:mm" />
        </el-form-item>
        <el-form-item label="最大预约">
          <el-input-number :min="1" :max="30" :value="7" />
          <span style="margin-left:8px;font-size:12px;color:#909399">学员最多可提前预约天数</span>
        </el-form-item>
        <el-form-item label="取消规则">
          <el-input-number :min="0" :max="48" :value="2" />
          <span style="margin-left:8px;font-size:12px;color:#909399">课前多少小时内不可取消预约</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary">保存设置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const bizHours = ref([new Date(2026, 0, 1, 9, 0), new Date(2026, 0, 1, 21, 0)])
</script>
