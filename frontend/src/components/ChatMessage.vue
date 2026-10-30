<script setup lang="ts">
import { AlertTriangle, Bot, Check, Copy, RefreshCw, UserRound } from 'lucide-vue-next'
import { computed, ref } from 'vue'

import CitationList from '@/components/CitationList.vue'
import MarkdownView from '@/components/MarkdownView.vue'
import ToolTrace from '@/components/ToolTrace.vue'
import { clockTime, formatMs } from '@/lib/format'
import { toast } from '@/stores/app'
import type { ChatMessage } from '@/types'

const props = defineProps<{ message: ChatMessage }>()
const emit = defineEmits<{ regenerate: [] }>()

const copied = ref(false)
const isUser = computed(() => props.message.role === 'user')
const traceCount = computed(
  () => (props.message.think?.length ?? 0) + (props.message.tools?.length ?? 0),
)
const showTrace = computed(() => !isUser.value && traceCount.value > 0)
const showPending = computed(
  () => !isUser.value && props.message.streaming && !props.message.content,
)

async function copy() {
  try {
    await navigator.clipboard.writeText(props.message.content)
    copied.value = true
    window.setTimeout(() => (copied.value = false), 1400)
  } catch {
    toast('复制失败，请手动选择文本', 'error')
  }
}
</script>

<template>
  <article class="msg" :class="{ 'msg-user': isUser }">
    <div class="avatar" :class="{ 'avatar-bot': !isUser }">
      <UserRound v-if="isUser" :size="15" />
      <Bot v-else :size="17" />
    </div>

    <div class="msg-body">
      <div class="msg-meta">
        <span style="font-weight: 600; color: var(--text-2)">{{ isUser ? '你' : '智能客服' }}</span>
        <span v-if="message.created_at">{{ clockTime(message.created_at) }}</span>
        <template v-if="!isUser">
          <span v-if="message.meta?.elapsed_ms" class="trace-latency">
            {{ formatMs(message.meta.elapsed_ms) }}
          </span>
        </template>
      </div>

      <div v-if="isUser" class="bubble-user">{{ message.content }}</div>

      <template v-else>
        <div v-if="message.notices?.length" class="notice-list">
          <div v-for="notice in message.notices" :key="notice.code" class="notice-banner">
            <AlertTriangle :size="14" style="flex: 0 0 14px; margin-top: 2px" />
            <div style="min-width: 0">
              <div>{{ notice.message }}</div>
              <div v-if="notice.detail" class="notice-detail">{{ notice.detail }}</div>
            </div>
          </div>
        </div>

        <ToolTrace
          v-if="showTrace"
          :think="message.think ?? []"
          :tools="message.tools ?? []"
          :streaming="message.streaming"
        />

        <div class="bubble-bot">
          <div v-if="showPending" class="thinking-row">
            <span class="dots"><span /><span /><span /></span>
            {{ message.statusText || '正在生成回答…' }}
          </div>

          <MarkdownView v-if="message.content" :content="message.content" />
          <span v-if="message.streaming && message.content" class="streaming-caret" />
        </div>

        <div v-if="message.error" class="error-box" style="margin-top: 10px">
          <div>
            <strong>{{ message.error.message }}</strong>
            <pre v-if="message.error.detail">{{ message.error.detail }}</pre>
          </div>
        </div>

        <CitationList v-if="message.citations?.length" :items="message.citations" />

        <div v-if="!message.streaming" class="msg-actions">
          <button class="action-btn" :title="copied ? '已复制' : '复制回答'" @click="copy">
            <Check v-if="copied" :size="13" />
            <Copy v-else :size="13" />
            {{ copied ? '已复制' : '复制' }}
          </button>
          <button class="action-btn" title="重新生成" @click="emit('regenerate')">
            <RefreshCw :size="13" />
            重新生成
          </button>
        </div>
      </template>

      <div v-if="isUser" class="msg-actions">
        <button class="action-btn" @click="copy">
          <Copy :size="13" />
          复制
        </button>
      </div>
    </div>
  </article>
</template>
