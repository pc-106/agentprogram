<script setup lang="ts">
import {
  FileBarChart,
  Library,
  MessageSquare,
  Moon,
  Plus,
  Search,
  Settings,
  Sun,
  Trash2,
  Pin,
  PinOff,
  Sparkles,
} from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import ModeBadge from '@/components/ModeBadge.vue'
import { app, toggleTheme, toast } from '@/stores/app'
import {
  chat,
  loadSessions,
  removeSession,
  renameSession,
  selectSession,
  startNewChat,
  togglePin,
  visibleSessions,
} from '@/stores/chat'
import { relativeTime, truncate } from '@/lib/format'
import type { Session } from '@/types'

const router = useRouter()
const route = useRoute()
const editingId = ref<string | null>(null)
const editingTitle = ref('')

const sessions = computed(() => visibleSessions())
const activeSession = computed(() => chat.sessions.find((item) => item.id === chat.currentId))

const navItems = [
  { to: '/', icon: MessageSquare, label: '对话' },
  { to: '/knowledge', icon: Library, label: '知识库' },
  { to: '/report', icon: FileBarChart, label: '使用报告' },
  { to: '/settings', icon: Settings, label: '系统设置' },
]

function isActive(path: string): boolean {
  return path === '/' ? route.path === '/' : route.path.startsWith(path)
}

function closeOnMobile() {
  app.sidebarOpen = false
}

async function newChat() {
  startNewChat()
  await router.push('/')
  closeOnMobile()
}

async function openSession(session: Session) {
  if (session.id === chat.currentId) {
    closeOnMobile()
    return
  }
  await selectSession(session.id)
  if (route.path !== '/') await router.push('/')
  closeOnMobile()
}

function beginRename(session: Session) {
  editingId.value = session.id
  editingTitle.value = session.title
}

async function commitRename() {
  const id = editingId.value
  if (!id) return
  const title = editingTitle.value.trim()
  editingId.value = null
  if (!title) return
  await renameSession(id, title)
}

async function dropSession(session: Session, event: Event) {
  event.stopPropagation()
  await removeSession(session.id)
  if (!chat.currentId) await router.push('/')
}

async function reset() {
  if (!window.confirm('确定删除全部会话记录吗？此操作不可撤销。')) return
  await Promise.all(chat.sessions.map((session) => removeSession(session.id, true)))
  startNewChat()
  await loadSessions()
  await router.push('/')
  toast('已清空全部会话', 'success')
}
</script>

<template>
  <aside class="sidebar" :class="{ open: app.sidebarOpen }">
    <div class="sidebar-head">
      <div class="brand-logo">
        <Sparkles :size="19" />
      </div>
      <div class="brand-text">
        <span class="brand-title">扫地机器人智能客服</span>
        <span class="brand-sub">ReAct Agent · RAG 知识库</span>
      </div>
    </div>

    <div class="sidebar-actions">
      <button class="new-chat" @click="newChat">
        <Plus :size="16" />
        新建对话
      </button>
    </div>

    <nav class="nav-group">
      <router-link
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="nav-item"
        :class="{ active: isActive(item.to) }"
        @click="closeOnMobile"
      >
        <component :is="item.icon" :size="16" />
        {{ item.label }}
      </router-link>
    </nav>

    <div class="nav-divider" />

    <div class="sessions-head">
      <span>历史会话</span>
      <button
        v-if="chat.sessions.length"
        class="icon-btn danger"
        title="清空全部会话"
        @click="reset"
      >
        <Trash2 :size="13" />
      </button>
    </div>

    <div class="session-search">
      <Search :size="13" />
      <input v-model="chat.search" placeholder="搜索会话…" aria-label="搜索会话" />
    </div>

    <div class="session-list">
      <div
        v-for="session in sessions"
        :key="session.id"
        class="session-item"
        :class="{ active: session.id === chat.currentId }"
        @click="openSession(session)"
        @dblclick="beginRename(session)"
      >
        <div class="session-main">
          <input
            v-if="editingId === session.id"
            v-model="editingTitle"
            class="input"
            style="height: 26px; padding: 2px 6px; font-size: 12.5px"
            @click.stop
            @keydown.enter.prevent="commitRename"
            @keydown.esc="editingId = null"
            @blur="commitRename"
          />
          <template v-else>
            <div class="session-title">
              <Pin v-if="session.pinned" :size="10" style="margin-right: 4px; color: var(--accent)" />
              {{ session.title }}
            </div>
            <div class="session-preview">
              {{ truncate(session.last_message ?? '还没有消息', 34) }}
            </div>
          </template>
        </div>

        <div class="session-tools">
          <button
            class="icon-btn"
            :title="session.pinned ? '取消置顶' : '置顶'"
            @click.stop="togglePin(session)"
          >
            <component :is="session.pinned ? PinOff : Pin" :size="12" />
          </button>
          <button class="icon-btn danger" title="删除会话" @click="dropSession(session, $event)">
            <Trash2 :size="12" />
          </button>
        </div>
      </div>

      <p
        v-if="!sessions.length"
        style="font-size: 12px; color: var(--text-3); padding: 14px; text-align: center; line-height: 1.7"
      >
        还没有会话。<br />问一个问题试试，或使用「新建对话」。
      </p>
    </div>

    <div class="sidebar-foot">
      <ModeBadge :mode="chat.mode" />
      <div class="sidebar-foot-row">
        <span>v{{ app.config?.version ?? '2.0.0' }} · {{ relativeTime(activeSession?.updated_at) || '就绪' }}</span>
        <button class="icon-btn" :title="app.theme === 'dark' ? '切换到浅色' : '切换到深色'" @click="toggleTheme">
          <Sun v-if="app.theme === 'dark'" :size="15" />
          <Moon v-else :size="15" />
        </button>
      </div>
    </div>
  </aside>
</template>
