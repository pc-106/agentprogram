<script setup lang="ts">
import { FileBarChart, ShoppingBag, Sparkles, Wrench } from 'lucide-vue-next'
import { computed } from 'vue'

import { toolIcon } from '@/lib/icons'
import { app } from '@/stores/app'

const emit = defineEmits<{ pick: [text: string] }>()

const suggestions = [
  {
    icon: ShoppingBag,
    title: '选购顾问',
    desc: '预算 + 户型 + 是否养宠，给出具体机型方向',
    prompt: '80㎡、有宠物，3000 元以内选哪种扫地机器人？',
  },
  {
    icon: Wrench,
    title: '故障排查',
    desc: '描述现象，帮你按「现象 → 检测 → 修复」定位',
    prompt: '机器人回充失败，总是停在半路怎么办？',
  },
  {
    icon: Sparkles,
    title: '保养提醒',
    desc: '耗材寿命、清洗周期与更换标准',
    prompt: '滤网和主刷分别多久换一次？',
  },
  {
    icon: FileBarChart,
    title: '使用报告',
    desc: '读取真实使用记录，生成月度报告与建议',
    prompt: '生成我的使用报告',
  },
]

const tools = computed(() => {
  const icons = app.config?.tools ?? {}
  return (app.config?.tool_order ?? []).map((name) => ({
    name,
    label: icons[name]?.label ?? name,
    icon: icons[name]?.icon ?? '',
  }))
})
</script>

<template>
  <div class="empty-chat">
    <div class="empty-logo">
      <Sparkles :size="28" />
    </div>

    <h1 class="empty-title">有什么可以帮你的？</h1>
    <p class="empty-sub">
      我会先判断问题类型，再决定是否检索知识库、查询天气或读取你的使用记录。
      回答都会标明依据，遇到报告类需求会自动切换成报告写手。
    </p>

    <div class="suggest-grid">
      <button
        v-for="item in suggestions"
        :key="item.title"
        class="suggest-card"
        @click="emit('pick', item.prompt)"
      >
        <div class="suggest-icon">
          <component :is="item.icon" :size="16" />
        </div>
        <div style="min-width: 0">
          <div class="suggest-title">{{ item.title }}</div>
          <div class="suggest-desc">{{ item.desc }}</div>
        </div>
      </button>
    </div>

    <div v-if="tools.length" class="empty-tools">
      <span v-for="tool in tools" :key="tool.name" class="chip">
        <component :is="toolIcon(tool.icon)" :size="12" />
        {{ tool.label }}
      </span>
    </div>
  </div>
</template>
