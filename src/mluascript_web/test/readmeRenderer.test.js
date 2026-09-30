import assert from 'node:assert/strict'
import test from 'node:test'

import { readmeHeadingId, renderReadmeMarkdown } from '../src/features/readme/readmeRenderer.js'

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

test('README headings expose stable Unicode anchors with duplicate suffixes', () => {
  const html = renderReadmeMarkdown('# 功能概览\n\n## 功能概览\n\n## API v1.0')

  assert.equal(readmeHeadingId('功能概览'), '功能概览')
  assert.match(html, /<h1 id="功能概览">功能概览<\/h1>/)
  assert.match(html, /<h2 id="功能概览-1">功能概览<\/h2>/)
  assert.match(html, /<h2 id="api-v10">API v1\.0<\/h2>/)
})
