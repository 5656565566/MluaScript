<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import DOMPurify from 'dompurify'
import { renderReadmeMarkdown } from '../features/readme/readmeRenderer.js'

const props = defineProps({
  markdown: { type: String, default: '' },
})

const container = ref(null)
const renderedHtml = ref('')
const renderRevision = ref(0)
let themeObserver = null
let mermaidGeneration = 0

function sanitize(html) {
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true, svg: true, svgFilters: true, mathMl: true },
  })
}

async function renderMermaidDiagrams(generation) {
  const nodes = [...(container.value?.querySelectorAll('[data-readme-mermaid]') || [])]
  if (!nodes.length) return
  const module = await import('mermaid')
  if (generation !== mermaidGeneration) return
  const mermaid = module.default
  const dark = document.documentElement.getAttribute('data-theme') === 'dark'
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'strict',
    theme: dark ? 'dark' : 'default',
    fontFamily: 'var(--font-family, sans-serif)',
  })
  for (const [index, node] of nodes.entries()) {
    const source = node.textContent || ''
    try {
      const id = `readme-mermaid-${generation}-${index}`
      const result = await mermaid.render(id, source)
      if (generation !== mermaidGeneration) return
      node.innerHTML = sanitize(result.svg)
      node.classList.add('is-rendered')
      result.bindFunctions?.(node)
    } catch (error) {
      node.classList.add('has-error')
      node.textContent = `Mermaid 图表渲染失败\n${String(error?.message || error)}`
    }
  }
}

async function refresh() {
  mermaidGeneration += 1
  const generation = mermaidGeneration
  renderedHtml.value = sanitize(renderReadmeMarkdown(props.markdown))
  renderRevision.value += 1
  await nextTick()
  await renderMermaidDiagrams(generation)
}

watch(() => props.markdown, refresh, { immediate: true })

onMounted(() => {
  themeObserver = new MutationObserver(refresh)
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
})

onBeforeUnmount(() => {
  mermaidGeneration += 1
  themeObserver?.disconnect()
})
</script>

<template>
  <article
    :key="renderRevision"
    ref="container"
    class="readme-renderer markdown-body"
    v-html="renderedHtml"
  ></article>
</template>

<style>
@import 'github-markdown-css/github-markdown.css';
@import 'katex/dist/katex.min.css';
@import 'markdown-it-texmath/css/texmath.css';

.readme-renderer.markdown-body {
  --fgColor-accent: var(--color-primary);
  --fgColor-default: var(--color-text-primary);
  --fgColor-muted: var(--color-text-secondary);
  --fgColor-danger: var(--color-danger);
  --fgColor-success: var(--color-success);
  --fgColor-attention: var(--color-warning);
  --fgColor-done: var(--color-info);
  --bgColor-default: transparent;
  --bgColor-muted: var(--color-surface-3);
  --bgColor-neutral-muted: var(--color-border-light);
  --bgColor-attention-muted: color-mix(in srgb, var(--color-warning) 12%, transparent);
  --borderColor-default: var(--color-border);
  --borderColor-muted: var(--color-border-light);
  --borderColor-neutral-muted: var(--color-border-light);
  --borderColor-accent-emphasis: var(--color-primary);
  --borderColor-attention-emphasis: var(--color-warning);
  --borderColor-danger-emphasis: var(--color-danger);
  --borderColor-done-emphasis: var(--color-info);
  --borderColor-success-emphasis: var(--color-success);
  --focus-outlineColor: var(--color-focus-ring);
  color: var(--color-text-primary);
  background: transparent;
  max-width: 980px;
  width: 100%;
  margin: 0 auto;
  padding: 24px 28px 48px;
  overflow-wrap: anywhere;
}

.readme-renderer .task-list-item {
  list-style: none;
}

.readme-renderer .task-list-item-checkbox {
  margin: 0 0.45em 0.25em -1.4em;
  accent-color: var(--color-primary);
}

.readme-renderer .readme-image-placeholder {
  color: var(--color-text-muted);
  font-style: italic;
}

.readme-renderer .readme-mermaid {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 96px;
  margin: 16px 0;
  padding: 16px;
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-surface-2);
  white-space: pre-wrap;
}

.readme-renderer .readme-mermaid.is-rendered {
  white-space: normal;
}

.readme-renderer .readme-mermaid svg {
  max-width: 100%;
  height: auto;
}

.readme-renderer .readme-mermaid.has-error {
  justify-content: flex-start;
  color: var(--color-danger);
}

.readme-renderer .hljs-comment,
.readme-renderer .hljs-quote {
  color: var(--color-text-muted);
}

.readme-renderer .hljs-keyword,
.readme-renderer .hljs-selector-tag,
.readme-renderer .hljs-literal {
  color: var(--color-danger);
}

.readme-renderer .hljs-string,
.readme-renderer .hljs-doctag,
.readme-renderer .hljs-regexp {
  color: var(--color-success);
}

.readme-renderer .hljs-number,
.readme-renderer .hljs-symbol,
.readme-renderer .hljs-bullet {
  color: var(--color-warning);
}

.readme-renderer .hljs-title,
.readme-renderer .hljs-section,
.readme-renderer .hljs-attribute {
  color: var(--color-info);
}

.readme-renderer .katex-display {
  overflow-x: auto;
  overflow-y: hidden;
  padding: 4px 0;
}
</style>
