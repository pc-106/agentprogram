/** 后端 API 客户端：JSON 请求 + SSE 流式对话 */

const BASE = '/api'

export class ApiError extends Error {
  status: number
  detail?: string

  constructor(message: string, status = 0, detail?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(init.headers ?? {}) },
      ...init,
    })
  } catch (error) {
    throw new ApiError('无法连接后端服务，请确认 uvicorn 已启动。', 0, String(error))
  }

  if (!response.ok) {
    let message = `请求失败（HTTP ${response.status}）`
    let detail = ''
    try {
      const payload = await response.json()
      message = payload.message ?? payload.detail?.[0]?.msg ?? payload.detail ?? message
      detail = typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail ?? '')
    } catch {
      /* 忽略非 JSON 响应 */
    }
    throw new ApiError(String(message), response.status, detail)
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}

export type SseHandler = (data: Record<string, unknown>) => void

export interface StreamHandlers {
  [event: string]: SseHandler | undefined
}

/** 解析 SSE 缓冲，返回剩余未消费的内容 */
export function consumeSseBuffer(buffer: string, handlers: StreamHandlers): string {
  let rest = buffer
  let boundary = rest.indexOf('\n\n')
  while (boundary >= 0) {
    const block = rest.slice(0, boundary)
    rest = rest.slice(boundary + 2)
    dispatchSse(block, handlers)
    boundary = rest.indexOf('\n\n')
  }
  return rest
}

function dispatchSse(block: string, handlers: StreamHandlers) {
  let event = 'message'
  const dataLines: string[] = []
  for (const rawLine of block.split('\n')) {
    const line = rawLine.replace(/\r$/, '')
    if (line.startsWith('event:')) {
      event = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart())
    }
  }
  if (!dataLines.length) return
  let payload: Record<string, unknown> = {}
  try {
    payload = JSON.parse(dataLines.join('\n')) as Record<string, unknown>
  } catch {
    return
  }
  handlers[event]?.(payload)
}

export interface ChatStreamPayload {
  message: string
  session_id?: string | null
  intent?: 'chat' | 'report'
}

/** POST + ReadableStream 消费 SSE（EventSource 不支持 POST） */
export async function streamChat(
  payload: ChatStreamPayload,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response
  try {
    response = await fetch(`${BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(payload),
      signal,
    })
  } catch (error) {
    if ((error as Error).name === 'AbortError') return
    throw new ApiError('无法连接后端服务，请确认 uvicorn 已启动。', 0, String(error))
  }

  if (!response.ok || !response.body) {
    const text = await response.text().catch(() => '')
    throw new ApiError(`对话请求失败（HTTP ${response.status}）`, response.status, text)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    buffer = consumeSseBuffer(buffer, handlers)
  }
  buffer += decoder.decode()
  if (buffer.trim()) {
    consumeSseBuffer(`${buffer}\n\n`, handlers)
  }
}
