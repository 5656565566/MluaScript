from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


_EDGE = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe"
_WEB_ROOT = Path(__file__).resolve().parents[2] / "src/mluascript_web"


@pytest.mark.integration
@pytest.mark.skipif(os.name != "nt" or not _EDGE.is_file(), reason="Requires an installed Windows Edge browser")
def test_readme_renders_diagrams_math_themes_and_recovers_from_errors(tmp_path: Path) -> None:
    # Test a production build of the Vue component, including its SVG sanitizer and lazy imports.
    server = subprocess.Popen(
        ["node", "--input-type=module", "-e", '''
import { build, preview } from 'vite';
import vue from '@vitejs/plugin-vue';
import { writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const html = `<div id="app"></div><script type="module">
import { createApp, h, ref } from 'vue';
import mermaid from 'mermaid';
import ReadmeRenderer from 'readme-component';
const markdown = ref('');
window.setReadmeMarkdown = value => { markdown.value = value; };
window.getMermaidConfig = () => mermaid.mermaidAPI.getConfig();
createApp({ render: () => h(ReadmeRenderer, { markdown: markdown.value }) }).mount('#app');
window.readmeFixtureReady = true;
</script>`;
const root = process.argv[1];
writeFileSync(join(root, 'index.html'), html);
await build({
    configFile: false, root, plugins: [vue()], logLevel: 'error',
    resolve: { alias: {
        vue: fileURLToPath(import.meta.resolve('vue/dist/vue.runtime.esm-bundler.js')),
        mermaid: fileURLToPath(import.meta.resolve('mermaid')),
        'readme-component': resolve('src/components/ReadmeRenderer.vue'),
    } },
});
const server = await preview({ configFile: false, root, preview: { host: '127.0.0.1', port: 0 }, logLevel: 'error' });
console.log(JSON.stringify({ url: `http://127.0.0.1:${server.httpServer.address().port}/index.html` }));
process.stdin.resume();
process.stdin.on('end', () => server.httpServer.close(() => process.exit(0)));
''', str(tmp_path)],
        cwd=_WEB_ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        assert server.stdout is not None
        address = server.stdout.readline()
        assert address, server.stderr.read() if server.stderr else "Vite server did not start"
        url = json.loads(address)["url"]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=str(_EDGE), headless=True)
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                errors: list[str] = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(url)
                page.wait_for_function("window.readmeFixtureReady === true")
                diagrams = [
                    'flowchart LR\n A["中文开始"] --> B["结束"]',
                    'sequenceDiagram\n Alice->>Bob: Request\n Bob-->>Alice: Response',
                    'classDiagram\n ClassA --> ClassB\n ClassA : +name',
                    'stateDiagram-v2\n [*] --> Idle\n Idle --> Running\n Running --> [*]',
                    'erDiagram\n USER ||--o{ TASK : owns',
                    'gantt\n dateFormat YYYY-MM-DD\n section Work\n Task :2026-10-01, 2d',
                    'pie title Resources\n "CPU" : 40\n "Memory" : 60',
                    'mindmap\n root((Project))\n  Runtime\n  Frontend',
                    'flowchart LR\n A["$$x^2 + y^2$$"] --> B["Math"]',
                ]
                markdown = '# Rendering\n\nInline $e^{i\\pi}+1=0$.\n\n$$\\frac{1}{2}$$\n\n'
                markdown += '\n\n'.join(f'```mermaid\n{diagram}\n```' for diagram in diagrams)
                markdown += '\n\n<script>window.unsafeReadme = true</script>'
                page.evaluate("value => window.setReadmeMarkdown(value)", markdown)
                page.wait_for_function("document.querySelectorAll('.readme-mermaid.is-rendered svg').length === 9", timeout=60000)
                assert page.locator('.readme-mermaid.has-error').count() == 0
                assert '中文开始' in page.locator('.readme-mermaid').first.inner_text()
                assert page.locator('.readme-renderer .katex').count() >= 3
                assert page.locator('.readme-renderer script').count() == 0
                assert page.evaluate("window.unsafeReadme") is None
                config = page.evaluate("window.getMermaidConfig()")
                assert (config['layout'], config['look'], config['theme'], config['securityLevel']) == ('dagre', 'classic', 'default', 'strict')
                ids = page.locator('.readme-mermaid svg').evaluate_all("nodes => nodes.map(node => node.id)")
                assert len(ids) == len(set(ids))
                for svg in page.locator('.readme-mermaid svg').all():
                    box = svg.bounding_box()
                    assert box is not None and box['width'] > 20 and box['height'] > 20

                page.evaluate("document.documentElement.setAttribute('data-theme', 'dark')")
                page.wait_for_function("id => document.querySelector('.readme-mermaid svg')?.id !== id && document.querySelectorAll('.readme-mermaid.is-rendered svg').length === 9", arg=ids[0])
                assert page.evaluate("window.getMermaidConfig().theme") == 'dark'

                page.evaluate("value => window.setReadmeMarkdown(value)", '```mermaid\nnot a valid diagram\n```')
                page.locator('.readme-mermaid.has-error').wait_for()
                page.evaluate("value => window.setReadmeMarkdown(value)", '```mermaid\nflowchart LR\n A --> B\n```')
                page.locator('.readme-mermaid.is-rendered svg').wait_for()
                assert page.locator('.readme-mermaid.has-error').count() == 0
                assert errors == []
            finally:
                browser.close()
    finally:
        if server.stdin:
            server.stdin.close()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()
