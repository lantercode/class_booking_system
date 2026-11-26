<template>
  <router-view />
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { connect, disconnect } from '@/utils/notify'
import { startNotifySync, stopNotifySync } from '@/utils/notify-sync'

onMounted(() => {
  // 事件订阅与连接是否建立解耦：未登录时连接不发起，订阅保持空转
  startNotifySync()
  // 应用启动 / 刷新：已有 token 视为已登录，直接建立推送连接
  if (localStorage.getItem('token')) connect()
})

onBeforeUnmount(() => {
  stopNotifySync()
  disconnect()
})
</script>
