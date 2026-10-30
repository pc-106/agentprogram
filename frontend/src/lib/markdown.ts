/** Markdown 渲染（marked + DOMPurify） */

import DOMPurify from 'dompurify'
import { marked } from 'marked'

marked.setOptions({ gfm: true, breaks: true })

DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A') {
    node.setAttribute('target', '_blank')
    node.setAttribute('rel', 'noopener noreferrer')
  }
})

export function renderMarkdown(source: string): string {
  if (!source) return ''
  try {
    const html = marked.parse(source, { async: false, gfm: true, breaks: true }) as string
    return DOMPurify.sanitize(html, { ADD_ATTR: ['target', 'rel'] })
  } catch {
    return DOMPurify.sanitize(`<p>${source.replace(/[<>&]/g, '')}</p>`)
  }
}
