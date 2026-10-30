<script setup lang="ts">
import { AlertTriangle, CheckCircle2, Info } from 'lucide-vue-next'

import { app } from '@/stores/app'
</script>

<template>
  <div class="toast-host">
    <div v-for="item in app.toasts" :key="item.id" class="toast" :class="item.kind">
      <CheckCircle2 v-if="item.kind === 'success'" :size="16" style="color: var(--good)" />
      <AlertTriangle v-else-if="item.kind === 'error'" :size="16" style="color: var(--bad)" />
      <Info v-else :size="16" style="color: var(--accent)" />
      <span>{{ item.text }}</span>
    </div>
  </div>
</template>
