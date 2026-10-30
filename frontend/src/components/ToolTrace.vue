<script setup lang="ts">
import { Brain, ChevronDown, Sparkles } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'

import { toolIcon } from '@/lib/icons'
import { argText, formatMs } from '@/lib/format'
import type { ToolTraceItem } from '@/types'

const props = defineProps<{
  think: string[]
  tools: ToolTraceItem[]
  streaming?: boolean
  elapsedMs?: number
}>()

const open = ref(Boolean(props.streaming))

watch(
  () => props.streaming,
  (streaming) => {
    if (!streaming) open.value = false
  },
)

const pending = computed(() => props.tools.some((tool) => tool.ok === null || tool.ok === undefined))
const summary = computed(() => {
  if (props.streaming && !props.tools.length) return '正在思考…'
  const parts = [`${props.tools.length} 个工具`]
  if (props.think.length) parts.push(`${props.think.length} 段思考`)
  return parts.join(' · ')
})
</script>

<template>
  <section class="trace">
    <button class="trace-head" @click="open = !open">
      <Sparkles :size="14" style="color: var(--accent)" />
      <span class="trace-head-title">思考与工具调用</span>
      <span class="trace-head-meta">
        <span v-if="streaming && pending" class="dots"><span /><span /><span /></span>
        <span>{{ summary }}</span>
        <ChevronDown
          :size="14"
          :style="{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform .2s' }"
        />
      </span>
    </button>

    <div v-if="open" class="trace-body">
      <div v-for="(item, index) in think" :key="`think-${index}`" class="trace-item">
        <div class="trace-icon think"><Brain :size="13" /></div>
        <div class="trace-main">
          <div class="trace-text">{{ item }}</div>
        </div>
      </div>

      <div v-for="tool in tools" :key="tool.id" class="trace-item">
        <div class="trace-icon">
          <component :is="toolIcon(tool.icon ?? undefined)" :size="13" />
        </div>
        <div class="trace-main">
          <div class="trace-line">
            <span class="trace-name">{{ tool.label }}</span>
            <span v-if="tool.ok === true" class="chip chip-good" style="height: 19px; font-size: 10.5px">成功</span>
            <span v-else-if="tool.ok === false" class="chip chip-bad" style="height: 19px; font-size: 10.5px">失败</span>
            <span v-else class="chip" style="height: 19px; font-size: 10.5px">执行中</span>
            <span v-if="tool.latency_ms !== null && tool.latency_ms !== undefined" class="trace-latency">
              {{ formatMs(tool.latency_ms) }}
            </span>
          </div>
          <div class="trace-args">{{ argText(tool.args) }}</div>
          <div v-if="tool.note" class="trace-text" style="font-size: 11.5px; color: var(--text-3)">
            {{ tool.note }}
          </div>
          <div v-if="tool.preview" class="trace-preview">{{ tool.preview }}</div>
          <div v-if="tool.error" class="trace-preview" style="color: var(--bad)">
            {{ tool.error }}
          </div>
        </div>
      </div>

      <div v-if="!think.length && !tools.length" class="trace-text" style="color: var(--text-3)">
        正在准备上下文…
      </div>
    </div>
  </section>
</template>
