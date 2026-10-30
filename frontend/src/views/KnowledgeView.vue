<script setup lang="ts">
import {
  AlertTriangle,
  Boxes,
  CheckCircle2,
  Clock,
  Database,
  FileText,
  Layers,
  RefreshCw,
  Search,
  Sparkles,
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'

import TopBar from '@/components/TopBar.vue'
import ModeBadge from '@/components/ModeBadge.vue'
import { api } from '@/api/client'
import { formatBytes, formatMs, truncate } from '@/lib/format'
import { toast } from '@/stores/app'
import { chat } from '@/stores/chat'
import type { KbDocument, KbStatus, SearchResult } from '@/types'

const status = ref<KbStatus | null>(null)
const documents = ref<KbDocument[]>([])
const loading = ref(true)
const reindexing = ref(false)
const error = ref('')

const query = ref('')
const topK = ref(3)
const searching = ref(false)
const result = ref<SearchResult | null>(null)

const totalChunks = computed(() => status.value?.chunks ?? 0)
const okDocs = computed(() => documents.value.filter((doc) => doc.ok).length)

onMounted(load)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await api.get<{ documents: KbDocument[]; status: KbStatus }>('/kb/documents')
    documents.value = data.documents
    status.value = data.status
  } catch (err) {
    error.value = (err as Error).message
  } finally {
    loading.value = false
  }
}

async function search() {
  const keyword = query.value.trim()
  if (!keyword || searching.value) return
  searching.value = true
  try {
    result.value = await api.post<SearchResult>('/kb/search', { query: keyword, k: topK.value })
  } catch (err) {
    toast((err as Error).message, 'error')
  } finally {
    searching.value = false
  }
}

async function reindex() {
  if (reindexing.value) return
  reindexing.value = true
  try {
    const data = await api.post<{ took_ms: number; status: KbStatus }>('/kb/reindex')
    status.value = data.status
    toast(`索引已重建：${data.status.chunks} 个片段，用时 ${formatMs(data.took_ms)}`, 'success')
    await load()
  } catch (err) {
    toast((err as Error).message, 'error')
  } finally {
    reindexing.value = false
  }
}
</script>

<template>
  <TopBar title="知识库" sub="本地 BM25 索引 · 原工程 ragagent/data 目录">
    <template #actions>
      <ModeBadge :mode="chat.mode" />
      <button class="btn btn-sm" :disabled="reindexing" @click="reindex">
        <RefreshCw :size="14" :class="{ spin: reindexing }" />
        {{ reindexing ? '重建中…' : '重建索引' }}
      </button>
    </template>
  </TopBar>

  <div class="view-scroll">
    <div class="view">
      <div class="view-head">
        <h1 class="view-title">知识库</h1>
        <p class="view-sub">
          直接读取 <code class="kbd">ragagent/data</code> 下的 TXT / PDF，按问答条目切块后建立
          BM25 倒排索引。离线模式下它就是 <code class="kbd">rag_summarize</code> 工具的数据源。
        </p>
      </div>

      <div v-if="error" class="error-box" style="margin-bottom: 16px">{{ error }}</div>

      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-label"><FileText :size="13" /> 文档</div>
          <div class="stat-value">{{ documents.length }}<span class="stat-unit">份</span></div>
          <div class="stat-foot">{{ okDocs }} 份已成功索引</div>
        </div>
        <div class="stat-card">
          <div class="stat-label"><Layers :size="13" /> 知识片段</div>
          <div class="stat-value">{{ totalChunks }}<span class="stat-unit">块</span></div>
          <div class="stat-foot">平均 {{ status?.avg_chunk_terms ?? 0 }} 词/块</div>
        </div>
        <div class="stat-card">
          <div class="stat-label"><Boxes :size="13" /> 词表规模</div>
          <div class="stat-value">{{ (status?.vocab ?? 0).toLocaleString() }}</div>
          <div class="stat-foot">分词器：{{ status?.tokenizer ?? '—' }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label"><Clock :size="13" /> 构建耗时</div>
          <div class="stat-value">{{ formatMs(status?.build_ms) }}</div>
          <div class="stat-foot">{{ status?.built_at ?? '—' }}</div>
        </div>
      </div>

      <div class="section-grid">
        <section class="panel">
          <div class="panel-head">
            <Database :size="15" style="color: var(--accent)" />
            <span class="card-title">文档清单</span>
            <span class="chip" style="margin-left: auto">{{ documents.length }} 份</span>
          </div>
          <div class="panel-body flush">
            <table class="data-table">
              <thead>
                <tr>
                  <th>文件</th>
                  <th>类型</th>
                  <th>片段</th>
                  <th>大小</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="doc in documents" :key="doc.name">
                  <td>
                    <div class="file-name">
                      <FileText :size="13" style="color: var(--text-3); flex: 0 0 auto" />
                      <span :title="doc.name">{{ doc.name.trim() }}</span>
                    </div>
                    <div class="mono" style="margin-top: 2px">{{ doc.title }}</div>
                  </td>
                  <td><span class="chip" style="height: 22px; font-size: 11px">{{ doc.type.toUpperCase() }}</span></td>
                  <td>{{ doc.chunks }}</td>
                  <td class="mono">{{ formatBytes(doc.size) }}</td>
                  <td>
                    <span v-if="doc.ok" class="chip chip-good" style="height: 22px; font-size: 11px">
                      <CheckCircle2 :size="11" /> 已索引
                    </span>
                    <span v-else class="chip chip-warn" style="height: 22px; font-size: 11px" :title="doc.reason">
                      <AlertTriangle :size="11" /> 跳过
                    </span>
                  </td>
                </tr>
                <tr v-if="!documents.length">
                  <td colspan="5" style="text-align: center; color: var(--text-3); padding: 24px">
                    {{ loading ? '加载中…' : '没有找到数据文件' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <div style="display: flex; flex-direction: column; gap: 14px">
          <section class="panel">
            <div class="panel-head">
              <Search :size="15" style="color: var(--accent)" />
              <span class="card-title">检索测试</span>
              <span v-if="result" class="chip" style="margin-left: auto">{{ formatMs(result.took_ms) }}</span>
            </div>
            <div class="panel-body">
              <form class="search-row" @submit.prevent="search">
                <input v-model="query" class="input" placeholder="例如：滤网多久换一次" />
                <select v-model.number="topK" class="select" style="width: 84px; flex: 0 0 84px">
                  <option :value="1">Top1</option>
                  <option :value="3">Top3</option>
                  <option :value="5">Top5</option>
                </select>
                <button class="btn btn-primary" :disabled="searching || !query.trim()" type="submit">
                  <Search :size="14" />
                </button>
              </form>

              <div v-if="result" class="result-list">
                <div v-for="item in result.items" :key="item.id" class="result-card">
                  <div class="result-head">
                    <span class="chip chip-accent" style="height: 20px; font-size: 10.5px">
                      {{ item.source }}
                    </span>
                    <div class="score-bar">
                      <div
                        class="score-fill"
                        :style="{ width: `${Math.max(6, (item.score ?? 0) * 100)}%` }"
                      />
                    </div>
                    <span class="mono">{{ Math.round((item.score ?? 0) * 100) }}%</span>
                  </div>
                  <div class="result-title">{{ item.title }}</div>
                  <div class="result-text">{{ truncate(item.snippet, 220) }}</div>
                </div>
                <p v-if="!result.items.length" style="color: var(--text-3); font-size: 12.5px">
                  没有命中任何片段，换个说法试试。
                </p>
              </div>
              <p v-else style="color: var(--text-3); font-size: 12.5px; margin: 12px 0 0">
                输入问题，查看 BM25 实际召回的知识片段与得分。
              </p>
            </div>
          </section>

          <section class="panel">
            <div class="panel-head">
              <Sparkles :size="15" style="color: var(--accent)" />
              <span class="card-title">索引配置</span>
            </div>
            <div class="panel-body">
              <div class="kv-list">
                <div class="kv-row">
                  <span class="kv-key">检索内核</span>
                  <span class="kv-val">{{ status?.engine ?? '—' }}</span>
                </div>
                <div class="kv-row">
                  <span class="kv-key">向量模型</span>
                  <span class="kv-val mono">{{ status?.embedding_model ?? '—' }}</span>
                </div>
                <div class="kv-row">
                  <span class="kv-key">切块参数</span>
                  <span class="kv-val">{{ status?.chunk_size ?? '—' }} 字 / 重叠 {{ status?.chunk_overlap ?? '—' }} 字</span>
                </div>
                <div class="kv-row">
                  <span class="kv-key">召回条数</span>
                  <span class="kv-val">{{ status?.retrieve_k ?? '—' }}</span>
                </div>
                <div class="kv-row">
                  <span class="kv-key">Chroma 库</span>
                  <span class="kv-val">
                    <span :class="status?.chroma.exists ? 'chip chip-good' : 'chip chip-warn'" style="height: 22px; font-size: 11px">
                      {{ status?.chroma.exists ? '已建库' : '未建库' }}
                      <template v-if="status?.chroma.exists">
                        · {{ status?.chroma.count ?? '—' }} 条
                      </template>
                    </span>
                  </span>
                </div>
              </div>

              <div class="note" style="margin-top: 12px">
                <Sparkles :size="14" style="flex: 0 0 14px; margin-top: 2px; color: var(--accent)" />
                <span>
                  配置 <code class="kbd">DASHSCOPE_API_KEY</code> 后，真实 Agent 模式会改用
                  <code class="kbd">langchain-chroma</code> 向量库（需先运行原工程的建库脚本）；
                  当前离线模式的 BM25 索引不依赖任何 API。
                </span>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>
