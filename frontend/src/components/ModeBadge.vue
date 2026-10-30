<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ mode: 'demo' | 'real' }>()

const isReal = computed(() => props.mode === 'real')
const label = computed(() => (isReal.value ? 'Agent 线上模式' : '离线模式'))
const hint = computed(() =>
  isReal.value
    ? '已检测到 DASHSCOPE_API_KEY，使用 ragagent 的 ReAct Agent 调用真实模型'
    : '未配置 Key 或调用失败，使用本地知识库检索 + 规则模板回答',
)
</script>

<template>
  <span class="mode-pill" :class="isReal ? 'is-real' : 'is-demo'" :title="hint">
    <span class="mode-dot" :class="{ real: isReal }" />
    <span>{{ label }}</span>
  </span>
</template>
