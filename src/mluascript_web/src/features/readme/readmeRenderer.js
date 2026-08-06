import MarkdownIt from 'markdown-it'
import footnote from 'markdown-it-footnote'
import taskLists from 'markdown-it-task-lists'
import texmath from 'markdown-it-texmath'
import katex from 'katex'
import hljs from 'highlight.js/lib/core'
import bash from 'highlight.js/lib/languages/bash'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import lua from 'highlight.js/lib/languages/lua'
import plaintext from 'highlight.js/lib/languages/plaintext'
import python from 'highlight.js/lib/languages/python'
import xml from 'highlight.js/lib/languages/xml'
import yaml from 'highlight.js/lib/languages/yaml'

for (const [name, language] of Object.entries({ bash, javascript, json, lua, plaintext, python, xml, yaml })) {
  hljs.registerLanguage(name, language)
}
hljs.registerAliases(['js'], { languageName: 'javascript' })
hljs.registerAliases(['html', 'svg'], { languageName: 'xml' })
hljs.registerAliases(['yml'], { languageName: 'yaml' })

function highlightCode(source, language) {
  const normalized = String(language || '').trim().toLowerCase()
  if (!normalized || !hljs.getLanguage(normalized)) return ''
  return hljs.highlight(source, { language: normalized, ignoreIllegals: true }).value
}

const renderer = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: false,
  highlight: highlightCode,
})
  .use(taskLists, { enabled: false, label: true, labelAfter: true })
  .use(footnote)
  .use(texmath, {
    engine: katex,
    delimiters: ['dollars', 'beg_end'],
    katexOptions: {
      throwOnError: false,
      strict: 'warn',
      trust: false,
      output: 'htmlAndMathml',
    },
  })

const defaultFence = renderer.renderer.rules.fence
renderer.renderer.rules.fence = (tokens, index, options, env, self) => {
  const token = tokens[index]
  if (String(token.info || '').trim().toLowerCase() === 'mermaid') {
    return `<div class="readme-mermaid" data-readme-mermaid><code>${renderer.utils.escapeHtml(token.content)}</code></div>`
  }
  return defaultFence(tokens, index, options, env, self)
}

renderer.renderer.rules.image = (tokens, index) => {
  const token = tokens[index]
  const alt = renderer.utils.escapeHtml(token.content || '图片')
  const source = renderer.utils.escapeHtml(token.attrGet('src') || '')
  return `<span class="readme-image-placeholder">[图片：${alt}${source ? ` · ${source}` : ''}]</span>`
}

const defaultLinkOpen = renderer.renderer.rules.link_open
  || ((tokens, index, options, _env, self) => self.renderToken(tokens, index, options))
renderer.renderer.rules.link_open = (tokens, index, options, env, self) => {
  const href = tokens[index].attrGet('href') || ''
  if (/^https?:\/\//i.test(href)) {
    tokens[index].attrSet('target', '_blank')
    tokens[index].attrSet('rel', 'noopener noreferrer')
  }
  return defaultLinkOpen(tokens, index, options, env, self)
}

export function renderReadmeMarkdown(markdown) {
  return renderer.render(String(markdown || ''))
}
