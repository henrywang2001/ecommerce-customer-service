import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

/** 将 Markdown 文本渲染为经过 DOMPurify 净化的安全 HTML 字符串（严禁对原始字符串直接 v-html） */
export function renderMarkdown(src: string): string {
  if (!src) return ''
  const raw = md.render(src)
  return DOMPurify.sanitize(raw)
}
