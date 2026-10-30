import { reactive } from 'vue'

import { api, streamChat } from '@/api/client'
import type { ChatMessage, Citation, Session, ToolTraceItem } from '@/types'

import { toast } from './app'

const streamController: { current: AbortController | null } = { current: null }

export const chat = reactive({
  sessions: [] as Session[],
  currentId: null as string | null,
  messages: [] as ChatMessage[],
  loadingMessages: false,
  streaming: false,
  mode: 'demo' as 'demo' | 'real',
  search: '',
})

export function visibleSessions(): Session[] {
  const keyword = chat.search.trim().toLowerCase()
  if (!keyword) return chat.sessions
  return chat.sessions.filter(
    (session) =>
      session.title.toLowerCase().includes(keyword) ||
      (session.last_message ?? '').toLowerCase().includes(keyword),
  )
}

export async function loadSessions() {
  try {
    const data = await api.get<{ sessions: Session[] }>('/sessions')
    chat.sessions = data.sessions
  } catch {
    /* 会话列表失败不阻塞对话 */
  }
}

export async function selectSession(id: string) {
  if (chat.streaming) return
  chat.currentId = id
  chat.loadingMessages = true
  try {
    const data = await api.get<{ messages: ChatMessage[] }>(`/sessions/${id}`)
    chat.messages = data.messages.map((message) => ({
      ...message,
      tools: message.meta?.tools ?? [],
      citations: message.meta?.citations ?? [],
      notices: message.meta?.notices ?? [],
      think: [],
      error: message.meta?.error ?? null,
    }))
  } catch (error) {
    toast((error as Error).message, 'error')
  } finally {
    chat.loadingMessages = false
  }
}

export function startNewChat() {
  if (chat.streaming) stopStreaming()
  chat.currentId = null
  chat.messages = []
}

export async function removeSession(id: string, silent = false) {
  try {
    await api.delete(`/sessions/${id}`)
    chat.sessions = chat.sessions.filter((session) => session.id !== id)
    if (chat.currentId === id) startNewChat()
    if (!silent) toast('会话已删除', 'success')
  } catch (error) {
    toast((error as Error).message, 'error')
  }
}

export async function renameSession(id: string, title: string) {
  const clean = title.trim()
  if (!clean) return
  try {
    const data = await api.patch<{ session: Session }>(`/sessions/${id}`, { title: clean })
    const index = chat.sessions.findIndex((session) => session.id === id)
    if (index >= 0) chat.sessions[index] = data.session
  } catch (error) {
    toast((error as Error).message, 'error')
  }
}

export async function togglePin(session: Session) {
  try {
    await api.patch(`/sessions/${session.id}`, { pinned: !session.pinned })
    await loadSessions()
  } catch (error) {
    toast((error as Error).message, 'error')
  }
}

export function stopStreaming() {
  streamController.current?.abort()
  streamController.current = null
  chat.streaming = false
  const last = chat.messages[chat.messages.length - 1]
  if (last?.streaming) last.streaming = false
}

export async function sendMessage(text: string, intent: 'chat' | 'report' = 'chat') {
  const message = text.trim()
  if (!message || chat.streaming) return

  const userMessage: ChatMessage = {
    id: `local-${Date.now()}`,
    role: 'user',
    content: message,
  }
  const assistant = reactive<ChatMessage>({
    id: `stream-${Date.now()}`,
    role: 'assistant',
    content: '',
    streaming: true,
    think: [],
    tools: [],
    citations: [],
    notices: [],
    error: null,
  })
  chat.messages.push(userMessage, assistant)
  chat.streaming = true
  chat.mode = chat.mode || 'demo'

  const controller = new AbortController()
  streamController.current = controller
  const startedAt = performance.now()

  const toolById = (id: unknown): ToolTraceItem | undefined =>
    assistant.tools?.find((tool) => tool.id === String(id))

  try {
    await streamChat(
      { message, session_id: chat.currentId, intent },
      {
        meta: (data) => {
          if (!chat.currentId) chat.currentId = String(data.session_id ?? '')
          if (data.mode === 'real' || data.mode === 'demo') chat.mode = data.mode
        },
        status: (data) => {
          assistant.statusText = String(data.text ?? '')
        },
        think: (data) => {
          assistant.statusText = ''
          const value = String(data.text ?? '').trim()
          if (value) assistant.think?.push(value)
        },
        tool_call: (data) => {
          assistant.statusText = ''
          assistant.tools?.push({
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
          const tool = toolById(data.id)
          if (!tool) return
          tool.ok = Boolean(data.ok ?? true)
          tool.latency_ms = Number(data.latency_ms ?? 0)
          tool.preview = String(data.preview ?? '')
          tool.error = data.error ? String(data.error) : null
        },
        notice: (data) => {
          assistant.notices = assistant.notices ?? []
          const notice = {
            code: String(data.code ?? 'notice'),
            level: (data.level === 'info' ? 'info' : 'warn') as 'warn' | 'info',
            message: String(data.message ?? ''),
            detail: data.detail ? String(data.detail) : undefined,
          }
          if (!assistant.notices.some((item) => item.code === notice.code)) {
            assistant.notices.push(notice)
          }
        },
        citations: (data) => {
          assistant.citations = (data.items as Citation[]) ?? []
        },
        delta: (data) => {
          assistant.content += String(data.text ?? '')
        },
        error: (data) => {
          assistant.error = {
            code: data.code ? String(data.code) : undefined,
            message: String(data.message ?? '生成失败'),
            detail: data.detail ? String(data.detail) : undefined,
          }
        },
        done: (data) => {
          assistant.id = String(data.message_id ?? assistant.id)
          assistant.streaming = false
          assistant.statusText = ''
          if (data.mode === 'real' || data.mode === 'demo') chat.mode = data.mode
          assistant.meta = {
            mode: (data.mode as 'demo' | 'real') ?? chat.mode,
            intent,
            elapsed_ms: Number(data.elapsed_ms ?? Math.round(performance.now() - startedAt)),
            tools: assistant.tools ?? [],
            citations: assistant.citations ?? [],
            notices: assistant.notices ?? [],
            error: assistant.error ?? null,
          }
        },
      },
      controller.signal,
    )
  } catch (error) {
    if ((error as Error).name !== 'AbortError') {
      assistant.error = { message: (error as Error).message }
      toast((error as Error).message, 'error')
    }
  } finally {
    assistant.streaming = false
    chat.streaming = false
    streamController.current = null
    await loadSessions()
  }
}

export async function regenerate() {
  if (chat.streaming) return
  const messages = chat.messages
  let userIndex = -1
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index].role === 'user') {
      userIndex = index
      break
    }
  }
  if (userIndex < 0) return
  const text = messages[userIndex].content
  chat.messages = messages.slice(0, userIndex)
  await sendMessage(text, 'chat')
}
