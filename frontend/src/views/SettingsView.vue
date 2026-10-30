<script setup lang="ts">
import {
  AlertTriangle,
  CheckCircle2,
  Cpu,
  ExternalLink,
  FolderTree,
  KeyRound,
  ScrollText,
  Wrench,
} from 'lucide-vue-next'
import { computed, ref } from 'vue'

import ModeBadge from '@/components/ModeBadge.vue'
import TopBar from '@/components/TopBar.vue'
import { toolIcon } from '@/lib/icons'
import { app } from '@/stores/app'
import { chat } from '@/stores/chat'

type PromptKey = 'main' | 'rag' | 'report'

const promptTab = ref<PromptKey>('main')
const config = computed(() => app.config)
const mode = computed(() => config.value?.mode)
const prompts = computed(() => config.value?.prompts)
const promptText = computed(() => prompts.value?.[promptTab.value] ?? '')

const toolList = computed(() => {
  const data = config.value?.tools ?? {}
  return (config.value?.tool_order ?? []).map((name) => ({
    name,
    label: data[name]?.label ?? name,
    icon: data[name]?.icon ?? '',
    description: data[name]?.description ?? '',
    args: data[name]?.args ?? [],
    scene: data[name]?.scene ?? '',
  }))
})

const tabs: { key: PromptKey; label: string; file: string }[] = [
  { key: 'main', label: '主提示词', file: 'prompt/main_prompt.txt' },
  { key: 'rag', label: 'RAG 总结', file: 'prompt/rag_summarize.txt' },
  { key: 'report', label: '报告写手', file: 'prompt/report_prompt.txt' },
]
</script>

<template>
  <TopBar title="系统设置" sub="运行模式、模型参数、工具清单与原工程兼容说明">
    <template #actions>
      <ModeBadge :mode="chat.mode" />
      <a class="btn btn-sm" href="/api/docs" target="_blank" rel="noreferrer">
        接口文档
        <ExternalLink :size="13" />
      </a>
    </template>
  </TopBar>

  <div class="view-scroll">
    <div class="view">
      <div class="view-head">
        <h1 class="view-title">系统设置</h1>
        <p class="view-sub">
          新版前后端不修改原 <code class="kbd">ragagent/</code> 任何源码，所有适配都发生在启动时的兼容层里。
        </p>
      </div>

      <div v-if="!config" class="note">正在加载配置…</div>

      <template v-else>
        <section class="panel setting-section">
          <div class="panel-head">
            <Cpu :size="15" style="color: var(--accent)" />
            <span class="card-title">运行状态</span>
            <ModeBadge :mode="mode?.mode ?? 'demo'" style="margin-left: auto" />
          </div>
          <div class="panel-body">
            <div class="kv-list">
              <div class="kv-row">
                <span class="kv-key">当前模式</span>
                <span class="kv-val">
                  {{ mode?.mode === 'real' ? '真实 Agent（LangChain + 通义千问）' : '离线演示（本地 BM25 + 规则模板）' }}
                  <span v-if="mode?.fallback" class="chip chip-warn" style="margin-left: 6px">已降级</span>
                </span>
              </div>
              <div class="kv-row">
                <span class="kv-key">请求模式</span>
                <span class="kv-val mono">AGENT_MODE={{ mode?.requested }}</span>
              </div>
              <div class="kv-row">
                <span class="kv-key">API Key</span>
                <span class="kv-val">
                  <span :class="mode?.has_api_key ? 'chip chip-good' : 'chip chip-warn'" style="height: 22px; font-size: 11px">
                    <KeyRound :size="11" />
                    {{ mode?.has_api_key ? '已配置 DASHSCOPE_API_KEY' : '未配置' }}
                  </span>
                </span>
              </div>
              <div class="kv-row">
                <span class="kv-key">服务版本</span>
                <span class="kv-val mono">v{{ config.version }} · 已运行 {{ app.health?.uptime_seconds ?? 0 }} 秒</span>
              </div>
            </div>

            <div class="note note-accent" style="margin-top: 12px">
              <CheckCircle2 :size="14" style="flex: 0 0 14px; margin-top: 2px" />
              <span>{{ mode?.note }}</span>
            </div>

            <div v-if="mode?.real_error" class="note note-warn" style="margin-top: 10px">
              <AlertTriangle :size="14" style="flex: 0 0 14px; margin-top: 2px" />
              <span style="word-break: break-all">{{ mode.real_error }}</span>
            </div>
          </div>
        </section>

        <section class="panel setting-section">
          <div class="panel-head">
            <Cpu :size="15" style="color: var(--accent)" />
            <span class="card-title">模型与检索</span>
          </div>
          <div class="panel-body">
            <div class="kv-list">
              <div class="kv-row">
                <span class="kv-key">对话模型</span>
                <span class="kv-val mono">{{ config.models.chat }}</span>
              </div>
              <div class="kv-row">
                <span class="kv-key">向量模型</span>
                <span class="kv-val mono">{{ config.models.embedding }}</span>
              </div>
              <div class="kv-row">
                <span class="kv-key">Chroma 集合</span>
                <span class="kv-val mono">{{ config.models.collection }}</span>
              </div>
              <div class="kv-row">
                <span class="kv-key">切块 / 重叠</span>
                <span class="kv-val">{{ config.retrieval.chunk_size }} / {{ config.retrieval.chunk_overlap }} 字</span>
              </div>
              <div class="kv-row">
                <span class="kv-key">召回条数</span>
                <span class="kv-val">{{ config.retrieval.top_k }}</span>
              </div>
              <div class="kv-row">
                <span class="kv-key">知识库片段</span>
                <span class="kv-val">
                  {{ config.stats.kb.chunks }} 块 / {{ config.stats.kb.documents }} 份文档
                </span>
              </div>
            </div>
          </div>
        </section>

        <section class="panel setting-section">
          <div class="panel-head">
            <Wrench :size="15" style="color: var(--accent)" />
            <span class="card-title">工具清单</span>
            <span class="chip" style="margin-left: auto">{{ toolList.length }} 个</span>
          </div>
          <div class="panel-body">
            <div class="tool-grid">
              <div v-for="tool in toolList" :key="tool.name" class="tool-card">
                <div class="tool-icon">
                  <component :is="toolIcon(tool.icon)" :size="15" />
                </div>
                <div style="min-width: 0">
                  <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap">
                    <strong style="font-size: 12.5px">{{ tool.label }}</strong>
                    <code class="mono">{{ tool.name }}</code>
                  </div>
                  <div style="font-size: 12px; color: var(--text-2); margin-top: 2px">{{ tool.description }}</div>
                  <div v-if="tool.args.length" style="font-size: 11px; color: var(--text-3); margin-top: 4px">
                    参数：{{ tool.args.map((arg) => arg.label).join('、') }}
                  </div>
                  <div v-else style="font-size: 11px; color: var(--text-3); margin-top: 4px">无参数</div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="panel setting-section">
          <div class="panel-head">
            <ScrollText :size="15" style="color: var(--accent)" />
            <span class="card-title">系统提示词</span>
          </div>
          <div class="prompt-tabs">
            <button
              v-for="tab in tabs"
              :key="tab.key"
              class="prompt-tab"
              :class="{ active: promptTab === tab.key }"
              @click="promptTab = tab.key"
            >
              {{ tab.label }}
            </button>
          </div>
          <pre class="prompt-pre">{{ promptText }}</pre>
        </section>

        <section class="panel setting-section">
          <div class="panel-head">
            <FolderTree :size="15" style="color: var(--accent)" />
            <span class="card-title">原工程兼容层</span>
          </div>
          <div class="panel-body">
            <p style="font-size: 12.5px; color: var(--text-2); margin: 0 0 10px; line-height: 1.7">
              原工程直接运行会因三处「配置与文件不一致」失败。兼容层在启动时注入模块别名修正它们，
              原文件保持不变（可用哈希校验）：
            </p>
            <div class="kv-list">
              <div class="kv-row">
                <span class="kv-key">1 · 导入拼写</span>
                <span class="kv-val"><code class="kbd">utils.path_tools</code> → <code class="kbd">utils.path_tool</code></span>
              </div>
              <div class="kv-row">
                <span class="kv-key">2 · 配置扩展名</span>
                <span class="kv-val">代码读 <code class="kbd">*.yaml</code>，实际文件是 <code class="kbd">*.yml</code></span>
              </div>
              <div class="kv-row">
                <span class="kv-key">3 · 提示词目录</span>
                <span class="kv-val">配置写 <code class="kbd">prompts/</code>，实际目录是 <code class="kbd">prompt/</code></span>
              </div>
            </div>
            <div class="note" style="margin-top: 12px">
              <CheckCircle2 :size="14" style="flex: 0 0 14px; margin-top: 2px; color: var(--good)" />
              <span>兼容层已生效：{{ config.legacy.notes.length }} 项修正已应用。原工程目录：<code class="kbd">{{ config.paths.legacy }}</code></span>
            </div>
          </div>
        </section>
      </template>
    </div>
  </div>
</template>
