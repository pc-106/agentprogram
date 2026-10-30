<script setup lang="ts">
import { Menu } from 'lucide-vue-next'

import { app } from '@/stores/app'

defineProps<{ title: string; sub?: string }>()
</script>

<template>
  <header class="topbar">
    <button class="icon-btn mobile-only" aria-label="打开侧边栏" @click="app.sidebarOpen = true">
      <Menu :size="18" />
    </button>

    <div style="min-width: 0; flex: 1">
      <div class="topbar-title">{{ title }}</div>
      <div v-if="sub" class="topbar-sub">{{ sub }}</div>
    </div>

    <div class="topbar-actions">
      <slot name="actions" />
    </div>
  </header>
</template>
