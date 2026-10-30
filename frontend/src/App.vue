<script setup lang="ts">
import { onMounted } from 'vue'

import AppSidebar from '@/components/AppSidebar.vue'
import ToastHost from '@/components/ToastHost.vue'
import { app, loadApp } from '@/stores/app'
import { chat, loadSessions } from '@/stores/chat'

onMounted(async () => {
  await Promise.all([loadApp(), loadSessions()])
  // 模式徽标以运行时的 chat.mode 为准：启动时先同步健康检查结果，
  // 之后真实模式降级会通过 SSE 的 meta/done 事件实时更新
  if (app.health) chat.mode = app.health.mode
})
</script>

<template>
  <div class="app-shell">
    <AppSidebar />
    <div v-if="app.sidebarOpen" class="sidebar-scrim" @click="app.sidebarOpen = false" />

    <main class="main-area">
      <div v-if="!app.ready && app.error" class="view">
        <div class="error-box" style="margin-top: 40px">
          <div>
            <strong>后端未连接</strong>
            <p style="margin: 4px 0 0">{{ app.error }}</p>
            <p style="margin: 8px 0 0; opacity: 0.8">
              请在 backend 目录执行 <code class="kbd">python run.py</code> 后刷新页面。
            </p>
          </div>
        </div>
      </div>
      <router-view v-else />
    </main>

    <ToastHost />
  </div>
</template>
