<script setup lang="ts">
import { FileText, Quote } from 'lucide-vue-next'
import { computed, ref } from 'vue'

import type { Citation } from '@/types'

const props = defineProps<{ items: Citation[] }>()

const activeId = ref<string | null>(null)
const active = computed(() => props.items.find((item) => item.id === activeId.value) ?? null)

function toggle(item: Citation) {
  activeId.value = activeId.value === item.id ? null : item.id
}
</script>

<template>
  <div v-if="items.length" class="citations">
    <div class="citations-head">
      <Quote :size="12" />
      知识库引用 · {{ items.length }} 条
      <span class="citation-tip">点击查看检索原文</span>
    </div>

    <div class="citation-list">
      <button
        v-for="item in items"
        :key="item.id"
        class="citation"
        :class="{ active: activeId === item.id }"
        :title="item.snippet"
        @click="toggle(item)"
      >
        <FileText :size="11" />
        {{ item.source }}
        <span v-if="typeof item.score === 'number'" class="citation-score">
          {{ Math.round(item.score * 100) }}%
        </span>
        <span v-else class="citation-score">#{{ item.rank }}</span>
      </button>
    </div>

    <div v-if="active" class="citation-detail">
      <div class="citation-detail-head">
        <span>{{ active.source }}</span>
        <span v-if="active.title">· {{ active.title }}</span>
      </div>
      <div class="citation-detail-text">{{ active.snippet }}</div>
    </div>
  </div>
</template>
