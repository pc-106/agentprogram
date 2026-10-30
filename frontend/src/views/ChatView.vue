<script setup lang="ts">
import { FileBarChart, Plus } from 'lucide-vue-next'
import { computed, nextTick, ref, watch } from 'vue'

import ChatComposer from '@/components/ChatComposer.vue'
import ChatMessage from '@/components/ChatMessage.vue'
import EmptyChat from '@/components/EmptyChat.vue'
import ModeBadge from '@/components/ModeBadge.vue'
import TopBar from '@/components/TopBar.vue'
import { app } from '@/stores/app'
import { chat, regenerate, sendMessage, startNewChat, stopStreaming } from '@/stores/chat'

const scroller = ref<HTMLElement | null>(null)

const currentSession = computed(() => chat.sessions.find((session) => session.id === chat.currentId))
const title = computed(() => currentSession.value?.title ?? '新对话')
const sub = computed(() => {
  const mode = chat.mode === 'real' ? '真实 Agent 模式 · 通义千问' : '离线演示模式 · 本地知识库检索'
  const count = chat.messages.length
  return count ? `${mode} · ${count} 条消息` : mode
})
const samples = computed(() => app.config?.samples ?? [])

function scrollToBottom(force = false) {
  const element = scroller.value
  if (!element) return
  const nearBottom = element.scrollHeight - element.scrollTop - element.clientHeight < 200
  if (force || nearBottom) {
    element.scrollTop = element.scrollHeight
  }
}

watch(
  () => chat.messages.length,
  () => nextTick(() => scrollToBottom(true)),
)
watch(
  () => chat.messages[chat.messages.length - 1]?.content,
  () => nextTick(() => scrollToBottom()),
)
watch(
  () => chat.currentId,
  () => nextTick(() => scrollToBottom(true)),
)

async function onSend(text: string) {
  scrollToBottom(true)
  await sendMessage(text, 'chat')
}

async function onReport() {
  scrollToBottom(true)
  await sendMessage('生成我的使用报告', 'report')
}
</script>

<template>
  <TopBar :title="title" :sub="sub">
    <template #actions>
      <ModeBadge :mode="chat.mode" />
      <button class="btn btn-sm" title="生成个人使用报告" @click="onReport">
        <FileBarChart :size="14" />
        <span class="hide-sm">生成报告</span>
      </button>
      <button class="btn btn-sm" title="新建对话" @click="startNewChat">
        <Plus :size="15" />
        <span class="hide-sm">新对话</span>
      </button>
    </template>
  </TopBar>

  <div ref="scroller" class="view-scroll" :class="{ 'is-empty': !chat.messages.length }">
    <EmptyChat v-if="!chat.messages.length" @pick="onSend" />

    <div v-else class="chat-wrap">
      <ChatMessage
        v-for="message in chat.messages"
        :key="message.id"
        :message="message"
        @regenerate="regenerate"
      />
      <div style="height: 16px" />
    </div>
  </div>

  <div class="composer-area">
    <ChatComposer
      :streaming="chat.streaming"
      :samples="samples"
      :show-samples="chat.messages.length === 0"
      @send="onSend"
      @stop="stopStreaming"
    />
  </div>
</template>
