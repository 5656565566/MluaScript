<script src="../ui/templateEditor/templateEditorComponent.js"></script>

<template>
  <n-modal
    v-model:show="visible"
    preset="card"
    class="template-editor-modal-shell"
    style="width: 100vw; max-width: 100vw;"
    title="模板配置"
    :bordered="false"
    size="huge"
    :mask-closable="false"
  >
    <div class="template-editor-modal">
      <div class="template-editor-main">
        <div class="template-editor-summary">
          <div class="summary-item">
            <span class="summary-label">模板 ID</span>
            <span class="summary-value">{{ localData.id || '未命名模板' }}</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">参数</span>
            <n-tag size="small" round>{{ stats.vars }}</n-tag>
          </div>
          <div class="summary-item">
            <span class="summary-label">必填</span>
            <n-tag size="small" type="warning" round>{{ stats.requiredVars }}</n-tag>
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
          <div class="summary-item summary-item-grow">
            <span class="summary-label">可绑定函数</span>
            <n-tag size="small" type="primary" round>{{ procedureOptions.length }}</n-tag>
          </div>
        </div>

        <div class="template-editor-content">
          <n-tabs v-model:value="activeTab" type="segment" animated class="editor-tabs">
            <n-tab-pane name="basic" tab="基本信息">
              <div class="pane-scroll">
                <n-form :model="localData" label-placement="top" require-mark-placement="right-hanging">
                  <div class="form-grid cols-2">
                    <n-form-item label="模板 ID" path="id" required>
                      <n-input v-model:value="localData.id" placeholder="例如: daily_battle" />
                    </n-form-item>
                    <n-form-item label="版本" path="v">
                      <n-input-number v-model:value="localData.v" :min="1" style="width: 100%;" />
                    </n-form-item>
                  </div>
                  <n-form-item label="名称 (可选)" path="t">
                    <n-input v-model:value="localData.t" placeholder="显示给用户的名称" />
                  </n-form-item>
                  <n-form-item label="描述 (可选)" path="d">
                    <n-input type="textarea" v-model:value="localData.d" placeholder="模板的功能描述、使用场景、注意事项" :rows="5" />
                  </n-form-item>
                </n-form>
              </div>
            </n-tab-pane>

            <n-tab-pane name="vars" tab="变量与参数">
              <div class="pane-scroll">
                <div class="toolbar-row">
                  <n-input v-model:value="variableSearch" clearable placeholder="搜索参数键名 / 名称 / 说明 / 类型" class="toolbar-search" />
                  <n-space>
                    <n-button @click="varsList.push(createVar())">添加参数</n-button>
                    <n-button quaternary @click="varsList.forEach(item => { item._showAdvanced = true })">展开全部高级</n-button>
                  </n-space>
                </div>

                <n-alert v-if="!varsList.length" type="default" :show-icon="false" style="margin-bottom: 16px;">
                  还没有定义任何参数。参数会在模板执行时暴露给用户填写，也可供任务和任务流引用。
                </n-alert>

                <n-dynamic-input
                  v-model:value="varsList"
                  :on-create="() => createVar()"
                  :show-sort-button="true"
                  class="vars-dynamic-input"
                >
                  <template #create-button-default>添加参数</template>
                  <template #default="{ value }">
                    <div v-show="!variableSearch || filteredVarsList.includes(value)" class="editor-card editor-card-full" :class="{ 'is-dependent': value.if?.k }">
                      <div class="card-header">
                        <div class="card-title-wrap">
                          <div class="card-title-row">
                            <n-tag size="small" :type="value.req ? 'warning' : 'default'">{{ value.tp }}</n-tag>
                            <span class="card-title">{{ value.t || value._key || '未命名参数' }}</span>
                            <n-text depth="3">{{ value._key || '未设置键名' }}</n-text>
                          </div>
                          <n-text depth="3" class="card-subtitle">{{ value.note || '建议补充该参数的用途和填写说明。' }}</n-text>
                        </div>
                        <n-space>
                          <n-button size="small" quaternary @click="duplicateVar(value)">复制</n-button>
                          <n-button size="small" quaternary @click="value._showAdvanced = !value._showAdvanced">
                            {{ value._showAdvanced ? '收起高级' : '展开高级' }}
                          </n-button>
                        </n-space>
                      </div>

                      <div class="form-grid cols-3 compact-grid">
                        <n-input v-model:value="value._key" placeholder="参数键名 (英文)" />
                        <n-input v-model:value="value.t" placeholder="显示名称" />
                        <n-select v-model:value="value.tp" :options="tpOptions" @update:value="() => {
                          value.def = defaultValueForType(value.tp)
                          if (value.tp !== 'int') { value.min = undefined; value.max = undefined }
                          if (value.tp !== 'enum') { value.oneOf = [] }
                        }" />
                      </div>

                      <n-collapse :expanded-names="value._showAdvanced ? ['advanced'] : []" class="ghost-collapse">
                        <n-collapse-item name="advanced">
                          <template #header>
                            <span></span>
                          </template>
                          <div class="advanced-panel">
                            <div v-if="value.if && value.if.k" class="sub-panel" style="margin-top: 0; margin-bottom: 12px; background: var(--n-color-modal); border-left: 3px solid var(--n-primary-color);">
                              <div class="sub-panel-title" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0;">
                                <span>受控关联参数</span>
                                <n-button size="small" type="error" quaternary @click="value.if = null">取消关联</n-button>
                              </div>
                              <n-text depth="3" style="display: block; margin-top: 4px;">
                                当参数 <n-tag size="small" type="info">{{ value.if.k }}</n-tag>
                                的值为 <n-tag size="small" type="warning">{{ value.if.eq !== '' && value.if.eq !== undefined ? String(value.if.eq) : '(任意)' }}</n-tag>
                                时，该参数才会显示并生效。
                              </n-text>
                            </div>

                            <div class="form-grid cols-2 compact-grid">
                              <div class="inline-switch-field">
                                <n-switch v-model:value="value.req" />
                                <span>必填参数</span>
                              </div>
                              <n-input v-model:value="value.note" placeholder="提示说明 (note)" />
                            </div>

                            <div v-if="value.tp === 'int'" class="form-grid cols-3 compact-grid">
                              <n-input-number v-model:value="value.def" placeholder="默认值" style="width: 100%;" />
                              <n-input-number v-model:value="value.min" placeholder="最小值" style="width: 100%;" />
                              <n-input-number v-model:value="value.max" placeholder="最大值" style="width: 100%;" />
                            </div>
                            <div v-else-if="value.tp === 'str' || value.tp === 'path'" class="form-grid cols-1 compact-grid">
                              <n-input v-model:value="value.def" placeholder="默认值" />
                            </div>
                            <div v-else-if="value.tp === 'bool'" class="inline-switch-field panel-block">
                              <n-switch v-model:value="value.def" />
                              <span>默认状态</span>
                            </div>

                            <div v-if="value.tp === 'enum'" class="sub-panel">
                              <div class="sub-panel-header">
                                <div>
                                  <div class="sub-panel-title">枚举选项</div>
                                </div>
                              </div>
                              <n-dynamic-input v-model:value="value.oneOf" :on-create="createEnumOption" class="enum-options-dynamic-input">
                                <template #default="{ value: opt }">
                                  <div class="child-card enum-option-card">
                                    <div class="form-grid cols-2 compact-grid" style="margin-bottom: 0;">
                                      <n-input v-model:value="opt.v" placeholder="值 (value)" />
                                      <n-input v-model:value="opt.t" placeholder="显示名称 (t)" />
                                    </div>
                                    <div style="margin-top: 8px;">
                                      <n-button size="small" dashed @click="handleAddDependentVar(value, opt.v)">以此选项作为条件添加关联参数</n-button>
                                    </div>
                                  </div>
                                </template>
                              </n-dynamic-input>
                              <div class="form-grid cols-1 compact-grid" style="margin-top: 12px;">
                                <n-input v-model:value="value.def" placeholder="默认值，填写 oneOf 中的 v" />
                              </div>
                            </div>

                            <div v-if="value.tp === 'bool'" style="margin-top: 12px;">
                              <n-button dashed @click="handleAddDependentVar(value, 'true')">以此开关开启作为条件添加关联参数</n-button>
                            </div>
                          </div>
                        </n-collapse-item>
                      </n-collapse>
                    </div>
                  </template>
                </n-dynamic-input>
              </div>
            </n-tab-pane>

            <n-tab-pane name="tasks" tab="任务">
              <div class="pane-scroll">
                <div class="toolbar-row">
                  <n-button @click="refreshProcedureDefinitions()">刷新函数列表</n-button>
                </div>

                <n-alert v-if="!procedureOptions.length" type="warning" :show-icon="false" style="margin-bottom: 16px;">
                  当前 Blockly 工作区没有可绑定的函数。请先创建至少一个“函数参数 args”的 有返回函数 或 无返回函数。
                </n-alert>

                <n-dynamic-input v-model:value="localData.tasks" :on-create="createTask" :show-sort-button="true">
                  <template #create-button-default>添加任务</template>
                  <template #default="{ value }">
                    <div class="editor-card task-editor-card">
                      <div class="task-editor-grid">
                        <n-input v-model:value="value.k" placeholder="任务 Key，例如 battle" />
                        <n-input v-model:value="value.t" placeholder="任务名称，例如 执行战斗" />
                        <n-select
                          v-model:value="value.fn"
                          :options="procedureOptions"
                          clearable
                          filterable
                          placeholder="选择 Blockly 函数"
                          @update:value="() => handleTaskFunctionChange(value)"
                        />
                      </div>

                      <div class="field-block">
                        <div class="field-label">任务变量</div>
                        <div class="picker-summary-row">
                          <div class="picker-summary-text">已选择 {{ value.args?.length || 0 }} 项</div>
                          <n-button size="small" @click="openTaskVarPicker(value)">选择任务变量</n-button>
                        </div>
                        <div class="task-selected-tags" v-if="value.args?.length">
                          <n-tag v-for="arg in value.args" :key="arg" size="small" type="info" round>{{ arg }}</n-tag>
                        </div>
                      </div>
                    </div>
                  </template>
                </n-dynamic-input>
              </div>
            </n-tab-pane>

            <n-tab-pane name="flows" tab="任务流">
              <div class="pane-scroll">
                <n-dynamic-input v-model:value="localData.flows" :on-create="createFlow" :show-sort-button="true">
                  <template #create-button-default>添加任务流</template>
                  <template #default="{ value }">
                    <div class="editor-card flow-editor-card">
                      <div class="form-grid cols-2 compact-grid">
                        <n-input v-model:value="value.k" placeholder="任务流 Key (主流程一般为 main)" />
                        <n-input v-model:value="value.t" placeholder="任务流名称 (可选)" />
                      </div>

                      <div class="field-block">
                        <div class="field-label">任务流全局参数</div>
                        <div class="picker-summary-row">
                          <div class="picker-summary-text">已选择 {{ value.g?.length || 0 }} 项</div>
                          <n-button size="small" @click="openFlowGlobalPicker(value)">选择任务流全局参数</n-button>
                        </div>
                        <div class="task-selected-tags" v-if="value.g?.length">
                          <n-tag v-for="globalArg in value.g" :key="globalArg" size="small" type="success" round>{{ globalArg }}</n-tag>
                        </div>
                      </div>

                      <n-divider style="margin: 18px 0 14px;">任务流步骤</n-divider>
                      <n-dynamic-input v-model:value="value.steps" :on-create="createFlowStep" :show-sort-button="true">
                        <template #default="{ value: step }">
                          <div class="child-card flow-step-card flow-step-card-wide">
                            <div class="step-topbar">
                              <div class="card-title-row">
                                <n-tag size="small">Step</n-tag>
                                <span class="card-title">{{ step.k || '未命名步骤' }}</span>
                              </div>
                              <n-button size="small" quaternary @click="fillArgsFromTask(step)">自动生成步骤默认值</n-button>
                            </div>
                            <div class="flow-step-grid compact-grid">
                              <n-input v-model:value="step.k" placeholder="步骤 ID" />
                              <n-select
                                v-model:value="step.task"
                                :options="taskOptions"
                                filterable
                                clearable
                                placeholder="搜索选择任务"
                                @update:value="() => handleStepTaskChange(step)"
                              />
                              <n-select v-model:value="step.onFail" :options="onFailOptions" />
                            </div>
                            <div class="field-block">
                              <div class="field-label">步骤默认值</div>
                              <div class="picker-summary-row">
                                <div class="picker-summary-text">已配置 {{ Object.keys(step.args || {}).length }} 项</div>
                                <n-button size="small" :disabled="!step.task" @click="openStepArgsPicker(value, step)">配置步骤默认值</n-button>
                              </div>
                              <div class="task-selected-tags" v-if="Object.keys(step.args || {}).length">
                                <n-tag v-for="[argKey, argValue] in Object.entries(step.args || {})" :key="argKey" size="small" type="warning" round>
                                  {{ argKey }} = {{ formatValuePreview(argValue) }}
                                </n-tag>
                              </div>
                            </div>
                          </div>
                        </template>
                      </n-dynamic-input>
                    </div>
                  </template>
                </n-dynamic-input>
              </div>
            </n-tab-pane>
          </n-tabs>
        </div>
      </div>

      <div class="template-editor-preview">
        <div class="preview-header">
          <div>
            <div class="preview-title">实时预览</div>
            <n-text depth="3">保存前可直接检查最终 JSON 结构</n-text>
          </div>
        </div>
        <div class="preview-scroll-shell">
          <n-scrollbar x-scrollable y-scrollable style="height: 70vh; width: 100%;">
            <pre class="preview-code">{{ templatePreview }}</pre>
          </n-scrollbar>
        </div>
      </div>
    </div>

    <template #footer>
      <n-space justify="space-between" align="center" style="width: 100%;">
        <n-text depth="3">模板定义会写入 Blockly 块的隐藏 JSON 字段中</n-text>
        <n-space>
          <n-button @click="handleClose">取消</n-button>
          <n-button type="primary" @click="handleSave">保存配置</n-button>
        </n-space>
      </n-space>
    </template>
  </n-modal>

  <n-modal
    v-model:show="pickerState.show"
    preset="card"
    style="width: 760px; max-width: 92vw;"
    :title="pickerState.title"
    :bordered="false"
    size="huge"
    :mask-closable="false"
  >
    <div class="picker-dialog-body">
      <n-alert v-if="pickerState.summary" type="info" :show-icon="false" style="margin-bottom: 16px;">
        {{ pickerState.summary }}
      </n-alert>
      <n-input
        v-model:value="pickerState.search"
        clearable
        placeholder="搜索键名 / 名称 / 来源"
        style="margin-bottom: 16px;"
      />
      <div class="picker-dialog-list">
        <div v-if="!pickerFilteredOptions.length" class="picker-empty-text">没有匹配项</div>
        <div v-else class="picker-option-grid">
          <label v-for="item in pickerFilteredOptions" :key="item.value" class="picker-option-card">
            <input v-model="pickerState.value" type="checkbox" :value="item.value" class="picker-option-checkbox" />
            <div class="picker-option-content">
              <div class="picker-option-title">{{ item.label }}</div>
              <n-text depth="3">{{ item.desc || '顶层变量' }}</n-text>
            </div>
          </label>
        </div>
      </div>
    </div>

    <template #footer>
      <n-space justify="end">
        <n-button @click="closePicker">取消</n-button>
        <n-button type="primary" @click="confirmPicker">确认</n-button>
      </n-space>
    </template>
  </n-modal>

  <n-modal
    v-model:show="stepArgEditorState.show"
    preset="card"
    style="width: 920px; max-width: 96vw;"
    title="配置步骤默认值"
    :bordered="false"
    size="huge"
    :mask-closable="false"
  >
    <div class="step-arg-editor-body">
      <n-alert type="info" :show-icon="false" style="margin-bottom: 16px;">
        按变量类型自动推导输入方式：文本参数填写字符串，布尔参数使用开关，整数参数使用数字输入，枚举参数直接选择枚举项。
      </n-alert>
      <div class="step-arg-editor-list">
        <div v-for="row in stepArgEditorState.rows" :key="row.key" class="step-arg-editor-row">
          <div class="step-arg-editor-enable">
            <input v-model="stepArgEditorState.selectedKeys" type="checkbox" :value="row.key" class="picker-option-checkbox" />
          </div>
          <div class="step-arg-editor-key">
            <div>{{ row.label }}</div>
            <n-text depth="3">{{ row.key }}</n-text>
          </div>
          <div class="step-arg-editor-inputs">
            <template v-if="row.editorType === 'bool'">
              <div class="inline-switch-field step-arg-inline-editor">
                <n-switch v-model:value="row.value" />
                <span>{{ row.value ? 'true' : 'false' }}</span>
              </div>
            </template>
            <template v-else-if="row.editorType === 'number'">
              <n-input-number v-model:value="row.value" style="width: 100%;" placeholder="填写数字默认值" />
            </template>
            <template v-else-if="row.editorType === 'enum'">
              <n-select
                v-model:value="row.value"
                :options="enumOptionsForKey(row.key)"
                filterable
                clearable
                placeholder="选择枚举默认值"
              />
            </template>
            <template v-else>
              <div class="step-arg-text-mode-grid">
                <n-input
                  v-if="row.sourceMode === 'literal'"
                  v-model:value="row.value"
                  placeholder="填写字符串默认值，例如 2-1"
                />
                <n-select
                  v-else
                  v-model:value="row.value"
                  :options="stepArgSourceOptions"
                  filterable
                  clearable
                  placeholder="选择模板变量作为默认值来源"
                />
                <n-button quaternary size="small" @click="row.sourceMode = row.sourceMode === 'literal' ? 'var' : 'literal'">
                  {{ row.sourceMode === 'literal' ? '改为引用模板变量' : '改为直接填写常量' }}
                </n-button>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <n-space justify="end">
        <n-button @click="closeStepArgEditor">取消</n-button>
        <n-button type="primary" @click="confirmStepArgEditor">确认</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped src="../ui/templateEditor/templateEditorModal.css"></style>
