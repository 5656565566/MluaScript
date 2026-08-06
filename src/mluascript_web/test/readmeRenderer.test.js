import assert from 'node:assert/strict'
import test from 'node:test'

import { renderReadmeMarkdown } from '../src/features/readme/readmeRenderer.js'

test('README renderer supports GitHub extensions, formulas, code and Mermaid placeholders', () => {
  const html = renderReadmeMarkdown(`
# Demo

- [x] ready

Inline $e^{i\\pi}+1=0$.

\`\`\`lua
local value = true
\`\`\`

\`\`\`mermaid
flowchart LR
  A --> B
\`\`\`
`)

  assert.match(html, /task-list-item-checkbox/)
  assert.match(html, /disabled=""/)
  assert.match(html, /class="katex"/)
  assert.match(html, /hljs-keyword/)
  assert.match(html, /data-readme-mermaid/)
})

test('README renderer escapes HTML, blocks images and isolates external links', () => {
  const html = renderReadmeMarkdown('<script>alert(1)</script>\n\n![logo](https://example.com/a.png)\n\n[site](https://example.com)')

  assert.doesNotMatch(html, /<script>/)
  assert.match(html, /&lt;script&gt;/)
  assert.doesNotMatch(html, /<img/)
  assert.match(html, /readme-image-placeholder/)
  assert.match(html, /target="_blank"/)
  assert.match(html, /rel="noopener noreferrer"/)
})
