/** 与后端约定的数据结构 */

export type Mode = 'demo' | 'real'

export interface ToolArg {
  name: string
  label: string
  type: string
}

export interface ToolMeta {
  label: string
  icon: string
  description: string
  args: ToolArg[]
  scene: string
}

export interface HealthResponse {
  ok: boolean
  version: string
  mode: Mode
  fallback: boolean
  uptime_seconds: number
  sessions: { sessions: number; messages: number }
  kb: { documents: number; chunks: number; built_at: string | null }
}

export interface ModeInfo {
  mode: Mode
  requested: string
  fallback: boolean
  has_api_key: boolean
  real_error: string | null
  note: string
}

export interface KbStatus {
  documents: number
  indexed_documents: number
  chunks: number
  vocab: number
  avg_chunk_terms: number
  built_at: string | null
  build_ms: number
  data_dir: string
  engine: string
  tokenizer: string
  collection: string
  embedding_model: string
  chunk_size: number
  chunk_overlap: number
  retrieve_k: number
  chroma: { path: string; exists: boolean; md5_store_exists: boolean; count?: number | null }
  legacy_dir: string
}

export interface AppConfig {
  version: string
  mode: ModeInfo
  models: { chat: string; embedding: string; collection: string }
  retrieval: { chunk_size: number; chunk_overlap: number; top_k: number }
  paths: { legacy: string; data: string; database: string; frontend_dist: string }
  legacy: { legacy_dir: string; exists: boolean; prepared: boolean; notes: string[] }
  tools: Record<string, ToolMeta>
  tool_order: string[]
  prompts: { main: string; rag: string; report: string }
  samples: string[]
  stats: { sessions: number; messages: number; kb: KbStatus }
}

export interface Session {
  id: string
  title: string
  mode: string
  pinned: boolean
  created_at: string
  updated_at: string
  message_count: number
  last_message?: string | null
}

export interface Citation {
  id: string
  source: string
  title: string
  score?: number
  rank: number
  snippet: string
  text?: string
}

export interface ToolTraceItem {
  id: string
  name: string
  label: string
  icon?: string
  args: Record<string, unknown>
  note?: string | null
  ok?: boolean | null
  latency_ms?: number | null
  preview?: string
  error?: string | null
}

export interface ChatError {
  code?: string
  message: string
  detail?: string
}

export interface Notice {
  code: string
  level?: 'warn' | 'info'
  message: string
  detail?: string
}

export interface MessageMeta {
  mode?: Mode
  intent?: string
  elapsed_ms?: number
  tools?: ToolTraceItem[]
  citations?: Citation[]
  notices?: Notice[]
  error?: ChatError | null
}

export interface ChatMessage {
  id: string
  session_id?: string
  role: 'user' | 'assistant'
  content: string
  meta?: MessageMeta
  created_at?: string
  streaming?: boolean
  statusText?: string
  think?: string[]
  tools?: ToolTraceItem[]
  citations?: Citation[]
  notices?: Notice[]
  error?: ChatError | null
  feedback?: 'up' | 'down'
}

export interface KbDocument {
  name: string
  type: string
  size: number
  md5: string
  chunks: number
  chars: number
  ok: boolean
  reason: string
  title: string
}

export interface SearchResult {
  query: string
  k: number
  took_ms: number
  items: Citation[]
}

export interface RecordUser {
  user_id: string
  months: string[]
  latest_month: string
  feature: string
}

export interface RecordsCatalog {
  users: RecordUser[]
  months: string[]
  total_records: number
}
