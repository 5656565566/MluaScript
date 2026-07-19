import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const componentUrl = new URL('../src/components/TemplateEditorModal.vue', import.meta.url)
const styleUrl = new URL('../src/ui/templateEditor/templateEditorModal.css', import.meta.url)
const resourceDialogUrl = new URL('../src/ui/templateEditor/TemplateResourceDialogs.vue', import.meta.url)
const workbenchUrl = new URL('../src/ui/templateEditor/TemplateFlowWorkbench.vue', import.meta.url)
const workbenchStyleUrl = new URL('../src/ui/templateEditor/templateFlowWorkbench.css', import.meta.url)

test('模板配置使用占满剩余高度的单一任务流工作区', async () => {
  const [component, style, resourceDialog, workbench, workbenchStyle] = await Promise.all([
    readFile(componentUrl, 'utf8'),
    readFile(styleUrl, 'utf8'),
    readFile(resourceDialogUrl, 'utf8'),
    readFile(workbenchUrl, 'utf8'),
    readFile(workbenchStyleUrl, 'utf8'),
  ])

  assert.doesNotMatch(component, /<n-tabs|<n-tab-pane/)
  assert.doesNotMatch(component, /\stitle="模板配置"/)
  assert.match(component, /template-editor-title-row[\s\S]*template-editor-title[\s\S]*aria-expanded="summaryExpanded"/)
  assert.doesNotMatch(component, /<template #header-extra>/)
  assert.match(component, /summary-toggle-icon[\s\S]*ChevronDown/)
  assert.match(component, /summary-overview-main[\s\S]*summary-actions[\s\S]*summary-stats/)
  assert.match(component, /summary-flow-row[\s\S]*PaginatedSearchSelect[\s\S]*搜索任务流名称或 Key/)
  assert.match(component, /summary-flow-row[\s\S]*summary-flow-controls[\s\S]*>添加<\/n-button>[\s\S]*删除\s*<\/n-button>/)
  assert.doesNotMatch(component, /任务、参数和任务流将在保存模板时统一提交/)
  assert.match(component, /autosaveStatusText[\s\S]*>关闭<\/n-button>/)
  assert.doesNotMatch(component, /保存配置|@click="handleSave"/)
  assert.match(component, /<TemplateFlowWorkbench/)
  assert.match(component, /<TemplateResourceDialogs/)
  assert.match(resourceDialog, /title="参数管理"/)
  assert.match(resourceDialog, /variablePagination\.options[\s\S]*v-model:page="variablePage"/)
  assert.match(resourceDialog, /allVariablesExpanded \? '收起高级' : '展开高级'/)
  assert.doesNotMatch(resourceDialog, /v-model:value="varsList"[^>]*show-sort-button/)
  assert.match(resourceDialog, /title="任务管理"/)
  assert.match(resourceDialog, /v-model:value="taskSearch"[\s\S]*搜索任务 Key \/ 名称 \/ Blockly 函数/)
  assert.match(resourceDialog, /taskPagination\.options[\s\S]*<n-pagination/)
  assert.doesNotMatch(resourceDialog, /v-model:value="localData\.tasks"[^>]*show-sort-button/)
  assert.match(style, /\.n-card\.template-editor-modal-shell\)\s*\{[^}]*height:\s*calc\(100dvh - 32px\)/s)
  assert.match(style, /> \.n-card-content\)\s*\{[^}]*flex:\s*1[^}]*min-height:\s*0[^}]*overflow:\s*hidden/s)
  assert.match(style, /\.template-editor-summary\s*\{[^}]*position:\s*absolute[^}]*z-index:\s*10/s)
  assert.match(style, /\.template-editor-summary\s*\{[^}]*width:\s*min\(784px, calc\(100vw - 96px\)\)/s)
  assert.match(style, /\.summary-overview-content,\s*\.summary-flow-content\s*\{[^}]*width:\s*min\(100%, 760px\)/s)
  assert.match(style, /\.summary-flow-row\s*\{[^}]*border-top:/s)
  assert.match(style, /\.summary-flow-content\s*\{[^}]*grid-template-columns:/s)
  assert.match(style, /\.summary-flow-controls\s*\{[^}]*grid-template-columns:[^}]*font-size:\s*13px/s)
  assert.match(style, /\.template-editor-workbench-scroll\s*\{[^}]*overflow:\s*auto[^}]*scrollbar-gutter:\s*stable/s)
  assert.match(workbenchStyle, /\.flow-workbench-root\s*\{[^}]*height:\s*100%[^}]*display:\s*flex[^}]*flex-direction:\s*column/s)
  assert.match(workbenchStyle, /\.flow-workbench\s*\{[^}]*flex:\s*1[^}]*min-height:\s*0/s)
  assert.match(workbenchStyle, /\.flow-step-rail\s*\{[^}]*overflow:\s*auto/s)
  assert.match(workbenchStyle, /\.flow-step-inspector\s*\{[^}]*overflow:\s*auto/s)
  assert.doesNotMatch(workbenchStyle, /\.flow-workbench\s*\{[^}]*min-height:\s*460px/s)
  assert.match(workbench, /参数覆盖[\s\S]*配置覆盖/)
  assert.match(workbench, /运行成功后[\s\S]*onSuccessOptions[\s\S]*运行失败后/)
  assert.doesNotMatch(workbench, /自动绑定同名参数/)
  assert.doesNotMatch(workbench, /class="flow-toolbar"|class="flow-toolbar-select"/)
  assert.doesNotMatch(workbench, /placeholder="选择任务流"/)
})
