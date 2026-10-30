<script setup lang="ts">
import { ArrowUp, Square } from 'lucide-vue-next'
import { nextTick, ref } from 'vue'

const props = defineProps<{
  streaming: boolean
  samples: string[]
  showSamples?: boolean
}>()

const emit = defineEmits<{ send: [text: string]; stop: [] }>()

const text = ref('')
const area = ref<HTMLTextAreaElement | null>(null)

function resize() {
  const element = area.value
  if (!element) return
  element.style.height = 'auto'
  element.style.height = `${Math.min(element.scrollHeight, 180)}px`
}

function submit() {
  const value = text.value.trim()
  if (!value || props.streaming) return
  emit('send', value)
  text.value = ''
  nextTick(() => {
    resize()
    area.value?.focus()
  })
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    submit()
  }
}

function useSample(sample: string) {
  text.value = sample
  nextTick(() => {
    resize()
    area.value?.focus()
  })
}

function focus() {
  area.value?.focus()
}

defineExpose({ focus })
</script>

<template>
  <div class="composer-inner">
    <div v-if="showSamples && samples.length" class="quick-row">
      <button v-for="sample in samples" :key="sample" class="quick-chip" @click="useSample(sample)">
        {{ sample }}
      </button>
    </div>

    <div class="composer">
      <textarea
        ref="area"
        v-model="text"
        rows="1"
        placeholder="问我扫地机器人的选购、故障、保养，或「生成我的使用报告」…"
        aria-label="输入问题"
        @input="resize"
        @keydown="onKeydown"
      />

      <div class="composer-bar">
        <span class="composer-hint">
          <span class="kbd">Enter</span> 发送 · <span class="kbd">Shift</span>
          <span class="kbd">Enter</span> 换行
        </span>

        <div style="margin-left: auto; display: flex; align-items: center; gap: 8px">
          <button
            v-if="streaming"
            class="send-btn"
            style="background: var(--surface-3); color: var(--text-2); box-shadow: none"
            title="停止生成"
            @click="emit('stop')"
          >
            <Square :size="13" fill="currentColor" />
          </button>
          <button
            v-else
            class="send-btn"
            :disabled="!text.trim()"
            title="发送"
            @click="submit"
          >
            <ArrowUp :size="17" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
