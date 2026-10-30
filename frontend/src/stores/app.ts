import { reactive } from 'vue'

import { api } from '@/api/client'
import type { AppConfig, HealthResponse } from '@/types'

export type ToastKind = 'info' | 'success' | 'error'

export interface Toast {
  id: number
  text: string
  kind: ToastKind
}

const THEME_KEY = 'sweeper-agent-theme'

export const app = reactive({
  config: null as AppConfig | null,
  health: null as HealthResponse | null,
  ready: false,
  error: '',
  theme: 'light' as 'light' | 'dark',
  sidebarOpen: false,
  toasts: [] as Toast[],
})

function applyTheme() {
  document.documentElement.dataset.theme = app.theme
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute('content', app.theme === 'dark' ? '#0b0e13' : '#0f9d8b')
}

export function initTheme() {
  const saved = localStorage.getItem(THEME_KEY)
  const prefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
  app.theme = saved === 'dark' || saved === 'light' ? (saved as 'light' | 'dark') : prefersDark ? 'dark' : 'light'
  applyTheme()
}

export function toggleTheme() {
  app.theme = app.theme === 'dark' ? 'light' : 'dark'
  localStorage.setItem(THEME_KEY, app.theme)
  applyTheme()
}

export async function loadApp() {
  try {
    const [health, config] = await Promise.all([
      api.get<HealthResponse>('/health'),
      api.get<AppConfig>('/system/config'),
    ])
    app.health = health
    app.config = config
    app.ready = true
    app.error = ''
  } catch (error) {
    app.error = (error as Error).message
  }
}

export function toast(text: string, kind: ToastKind = 'info') {
  const id = Date.now() + Math.random()
  app.toasts.push({ id, text, kind })
  window.setTimeout(() => {
    const index = app.toasts.findIndex((item) => item.id === id)
    if (index >= 0) app.toasts.splice(index, 1)
  }, 3600)
}
