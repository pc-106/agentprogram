/** 工具名 -> 图标组件（与后端 tools_meta 的 icon 字段对应） */

import type { Component } from 'vue'
import {
  BookOpen,
  Bot,
  CalendarDays,
  CloudSun,
  Database,
  FileText,
  MapPin,
  Sparkles,
  UserRound,
  Wrench,
} from 'lucide-vue-next'

const ICONS: Record<string, Component> = {
  'book-open': BookOpen,
  'cloud-sun': CloudSun,
  'map-pin': MapPin,
  'user-round': UserRound,
  'calendar-days': CalendarDays,
  database: Database,
  'file-text': FileText,
  bot: Bot,
  sparkles: Sparkles,
}

export function toolIcon(icon: string | undefined | null): Component {
  return (icon && ICONS[icon]) || Wrench
}
