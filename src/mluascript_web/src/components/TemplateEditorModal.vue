<script src="../ui/templateEditor/templateEditorComponent.js"></script>

<template>
  <n-modal
    v-model:show="visible"
    preset="card"
    class="template-editor-modal-shell"
    style="width: 100vw; max-width: 100vw;"
    :bordered="false"
    size="huge"
    :mask-closable="false"
  >
    <template #header>
      <div class="template-editor-header">
        <div class="template-editor-title-row">
          <div class="template-editor-title">模板配置</div>
          <n-button
            quaternary
            circle
            size="small"
            :aria-expanded="summaryExpanded"
            :aria-label="summaryExpanded ? '收起模板摘要' : '展开模板摘要'"
            @click="summaryExpanded = !summaryExpanded"
          >
            <template #icon>
              <n-icon class="summary-toggle-icon" :class="{ 'is-expanded': summaryExpanded }">
                <ChevronDown />
              </n-icon>
            </template>
          </n-button>
        </div>
        <div v-if="summaryExpanded" class="template-editor-summary">
          <div class="summary-overview-row">
            <div class="summary-overview-content">
              <div class="summary-overview-main">
                <div class="summary-item summary-template-name">
                  <span class="summary-label">模板</span>
                  <span class="summary-value">{{ localData.t || localData.id || '未命名模板' }}</span>
                </div>
                <n-space class="summary-actions" size="small">
                  <n-button size="small" @click="openSettingsDialog">模板设置</n-button>
                  <n-button size="small" @click="openVariableDialog">管理参数</n-button>
                  <n-button size="small" @click="openTaskDialog">管理任务</n-button>
                </n-space>
              </div>
              <div class="summary-stats">
                <div class="summary-item">
                  <span class="summary-label">参数</span>
                  <n-tag size="small" round>{{ stats.vars }}</n-tag>
                </div>
                <div class="summary-item">
                  <span class="summary-label">任务</span>
                  <n-tag size="small" type="info" round>{{ stats.tasks }}</n-tag>
                </div>
                <div class="summary-item">
                  <span class="summary-label">任务流</span>
                  <n-tag size="small" type="success" round>{{ stats.flows }}</n-tag>
                </div>
                <div class="summary-item">
                  <span class="summary-label">步骤</span>
                  <n-tag size="small" type="default" round>{{ stats.flowSteps }}</n-tag>
                </div>
              </div>
            </div>
          </div>

          <div class="summary-flow-row">
            <div class="summary-flow-content">
              <span class="summary-label">任务流</span>
              <div class="summary-flow-controls">
                <PaginatedSearchSelect
                  :value="selectedFlow ? selectedFlowIndex : null"
                  :options="flowOptions"
                  placeholder="暂无任务流"
                  search-placeholder="搜索任务流名称或 Key"
                  @update:value="selectFlow"
                />
                <n-space class="summary-flow-actions" size="small" :wrap="false">
                  <n-button size="small" type="primary" secondary @click="addFlow">添加</n-button>
                  <n-button
                    size="small"
                    type="error"
                    quaternary
                    :disabled="!selectedFlow"
                    @click="removeSelectedFlow"
                  >
                    删除
                  </n-button>
                </n-space>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <div class="template-editor-modal">
      <div class="template-editor-main">
        <div class="template-editor-content">
          <div class="template-editor-workbench-scroll">
            <TemplateFlowWorkbench :editor="flowEditor" />
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <n-space justify="space-between" align="center" style="width: 100%;">
        <n-text :type="autosaveStatus === 'error' ? 'error' : undefined" depth="3">
          {{ autosaveStatusText }}
        </n-text>
        <n-button :loading="isClosing" @click="handleClose">关闭</n-button>
      </n-space>
    </template>
  </n-modal>

  <TemplateResourceDialogs :editor="flowEditor" />
  <TemplateAuxiliaryDialogs :editor="flowEditor" />
</template>

<style scoped src="../ui/templateEditor/templateEditorModal.css"></style>
