<script setup lang="ts">
import { Check, Copy, Download, FileBarChart, RefreshCw, Sparkles, TriangleAlert, Users } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'

import MarkdownView from '@/components/MarkdownView.vue'
import ModeBadge from '@/components/ModeBadge.vue'
import ToolTrace from '@/components/ToolTrace.vue'
import TopBar from '@/components/TopBar.vue'
import { api, streamChat } from '@/api/client'
import { formatMs } from '@/lib/format'
import { toast } from '@/stores/app'
import { chat } from '@/stores/chat'
import type { Notice, RecordsCatalog, ToolTraceItem } from '@/types'

const catalog = ref<RecordsCatalog | null>(null)
const userId = ref('')
const month = ref('')
const generating = ref(false)
const report = ref('')
const tools = ref<ToolTraceItem[]>([])
const notices = ref<Notice[]>([])
const error = ref('')
const elapsed = ref(0)
const copied = ref(false)

const currentUser = computed(() => catalog.value?.users.find((user) => user.user_id === userId.value))
const months = computed(() => currentUser.value?.months ?? [])
const userCount = computed(() => catalog.value?.users.length ?? 0)

onMounted(load)

async function load() {
  try {
    const data = await api.get<RecordsCatalog>('/kb/records')
    catalog.value = data
    if (data.users.length) {
      userId.value = data.users[0].user_id
      month.value = data.users[0].latest_month
    }
  } catch (err) {
    error.value = (err as Error).message
  }
}

function pickUser(id: string) {
  userId.value = id
  const user = catalog.value?.users.find((item) => item.user_id === id)
  month.value = user?.latest_month ?? ''
}

async function generate() {
  if (generating.value || !userId.value || !month.value) return
  generating.value = true
  report.value = ''
  tools.value = []
  notices.value = []
  error.value = ''
  elapsed.value = 0

  const controller = new AbortController()
  try {
    await streamChat(
      {
        message: `生成用户 ${userId.value} 在 ${month.value} 的使用报告`,
        intent: 'report',
      },
      {
        tool_call: (data) => {
          tools.value.push({
            id: String(data.id ?? ''),
            name: String(data.name ?? ''),
            label: String(data.label ?? data.name ?? '工具'),
            icon: data.icon ? String(data.icon) : undefined,
            args: (data.args as Record<string, unknown>) ?? {},
            note: data.note ? String(data.note) : null,
            ok: null,
            latency_ms: null,
            preview: '',
          })
        },
        tool_result: (data) => {
          const tool = tools.value.find((item) => item.id === String(data.id))
          if (!tool) return
          tool.ok = Boolean(data.ok ?? true)
          tool.latency_ms = Number(data.latency_ms ?? 0)
          tool.preview = String(data.preview ?? '')
        },
        notice: (data) => {
          const code = String(data.code ?? 'notice')
          if (notices.value.some((item) => item.code === code)) return
          notices.value.push({
            code,
            level: data.level === 'info' ? 'info' : 'warn',
            message: String(data.message ?? ''),
            detail: data.detail ? String(data.detail) : undefined,
          })
        },
        delta: (data) => {
          report.value += String(data.text ?? '')
        },
        done: (data) => {
          elapsed.value = Number(data.elapsed_ms ?? 0)
        },
        error: (data) => {
          error.value = String(data.message ?? '生成失败')
        },
      },
      controller.signal,
    )
  } catch (err) {
    error.value = (err as Error).message
  } finally {
    generating.value = false
  }
}

async function copy() {
  if (!report.value) return
  try {
    await navigator.clipboard.writeText(report.value)
    copied.value = true
    window.setTimeout(() => (copied.value = false), 1500)
    toast('报告已复制到剪贴板', 'success')
  } catch {
    toast('复制失败', 'error')
  }
}

function download() {
  if (!report.value) return
  const blob = new Blob([report.value], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `使用报告-${userId.value}-${month.value}.md`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <TopBar title="使用报告" sub="读取 records.csv 的真实使用记录，生成月度报告与保养建议">
    <template #actions>
      <ModeBadge :mode="chat.mode" />
      <span class="chip">{{ userCount }} 位用户 · {{ catalog?.total_records ?? 0 }} 条记录</span>
    </template>
  </TopBar>

  <div class="view-scroll">
    <div class="view">
      <div class="view-head">
        <h1 class="view-title">使用报告</h1>
        <p class="view-sub">
          与原工程的报告流程一致：获取用户 ID → 获取月份 → 切换报告模式 → 读取使用记录 →
          检索保养资料，最后按 Markdown 输出。
        </p>
      </div>

      <div class="report-layout">
        <div style="display: flex; flex-direction: column; gap: 12px">
          <section class="panel">
            <div class="panel-head">
              <Users :size="15" style="color: var(--accent)" />
              <span class="card-title">选择用户</span>
            </div>
            <div class="panel-body" style="padding: 8px; max-height: 330px; overflow: auto">
              <div
                v-for="user in catalog?.users ?? []"
                :key="user.user_id"
                class="user-chip"
                :class="{ active: user.user_id === userId }"
                @click="pickUser(user.user_id)"
              >
                <div style="min-width: 0">
                  <div class="user-id">用户 {{ user.user_id }}</div>
                  <div class="user-feature">{{ user.feature }}</div>
                </div>
                <span class="chip" style="height: 20px; font-size: 10.5px">{{ user.months.length }} 月</span>
              </div>
            </div>
          </section>

          <section class="panel">
            <div class="panel-head">
              <FileBarChart :size="15" style="color: var(--accent)" />
              <span class="card-title">报告参数</span>
            </div>
            <div class="panel-body">
              <label class="stat-label" style="margin-bottom: 6px">统计月份</label>
              <select v-model="month" class="select">
                <option v-for="item in months" :key="item" :value="item">{{ item }}</option>
              </select>

              <button
                class="btn btn-primary"
                style="width: 100%; margin-top: 12px; height: 40px"
                :disabled="generating || !months.length"
                @click="generate"
              >
                <RefreshCw :size="15" :class="{ spin: generating }" />
                {{ generating ? '生成中…' : report ? '重新生成报告' : '生成报告' }}
              </button>

              <div class="note" style="margin-top: 12px">
                <Sparkles :size="14" style="flex: 0 0 14px; margin-top: 2px; color: var(--accent)" />
                <span>离线模式下报告由规则模板合成，所有结论都能追溯到记录字段；配置 API Key 后由模型重写。</span>
              </div>
            </div>
          </section>
        </div>

        <section class="panel" style="min-height: 480px">
          <div class="report-toolbar">
            <FileBarChart :size="15" style="color: var(--accent)" />
            <strong style="font-size: 13px">报告预览</strong>
            <span v-if="report" class="chip chip-accent">{{ userId }} · {{ month }}</span>
            <span v-if="elapsed" class="chip">{{ formatMs(elapsed) }}</span>

            <div style="margin-left: auto; display: flex; gap: 6px">
              <button class="btn btn-sm" :disabled="!report" @click="copy">
                <Check v-if="copied" :size="13" />
                <Copy v-else :size="13" />
                {{ copied ? '已复制' : '复制' }}
              </button>
              <button class="btn btn-sm" :disabled="!report" @click="download">
                <Download :size="13" />
                下载
              </button>
            </div>
          </div>

          <div class="report-preview">
            <div v-if="notices.length" class="notice-list">
              <div v-for="notice in notices" :key="notice.code" class="notice-banner">
                <TriangleAlert :size="14" style="flex: 0 0 14px; margin-top: 2px" />
                <div style="min-width: 0">
                  <div>{{ notice.message }}</div>
                  <div v-if="notice.detail" class="notice-detail">{{ notice.detail }}</div>
                </div>
              </div>
            </div>

            <ToolTrace
              v-if="tools.length"
              :think="[]"
              :tools="tools"
              :streaming="generating"
              style="margin-bottom: 16px"
            />

            <div v-if="error" class="error-box" style="margin-bottom: 14px">{{ error }}</div>

            <MarkdownView v-if="report" :content="report" />

            <div v-else class="report-empty">
              <FileBarChart :size="34" style="opacity: 0.35" />
              <div v-if="generating">正在按报告流程执行…</div>
              <div v-else>
                选择左侧用户与月份，点击「生成报告」<br />
                即可看到真实的工具调用轨迹与 Markdown 报告
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>
