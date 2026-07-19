<script>
import { computed, nextTick, ref, watch } from 'vue'
import {
  NAlert,
  NButton,
  NCollapse,
  NCollapseItem,
  NDynamicInput,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NPagination,
  NPopconfirm,
  NSelect,
  NSpace,
  NSwitch,
  NTag,
  NText,
} from 'naive-ui'
import { paginateSelectOptions } from './paginatedSelect.js'
import { filterTaskDefinitions, TASK_RESOURCE_PAGE_SIZE } from './taskResourceList.js'

const VARIABLE_RESOURCE_PAGE_SIZE = 4

export default {
  components: {
    NAlert,
    NButton,
    NCollapse,
    NCollapseItem,
    NDynamicInput,
    NForm,
    NFormItem,
    NInput,
    NInputNumber,
    NModal,
    NPagination,
    NPopconfirm,
    NSelect,
    NSpace,
    NSwitch,
    NTag,
    NText,
  },
  props: {
    editor: {
      type: Object,
      required: true,
    },
  },
  setup(props) {
    const variablePage = ref(1)
    const taskSearch = ref('')
    const taskPage = ref(1)
    const variableList = computed(() => props.editor.varsList.value)
    const variablePagination = computed(() => paginateSelectOptions(
      props.editor.filteredVarsList.value,
      variablePage.value,
      VARIABLE_RESOURCE_PAGE_SIZE,
    ))
    const allVariablesExpanded = computed(() => (
      variableList.value.length > 0
      && variableList.value.every(item => item._showAdvanced)
    ))
    const taskList = computed(() => props.editor.localData.value.tasks || [])
    const filteredTasks = computed(() => filterTaskDefinitions(taskList.value, taskSearch.value))
    const taskPagination = computed(() => paginateSelectOptions(
      filteredTasks.value,
      taskPage.value,
      TASK_RESOURCE_PAGE_SIZE,
    ))

    watch(() => props.editor.variableSearch.value, () => {
      variablePage.value = 1
    })
    watch(taskSearch, () => {
      taskPage.value = 1
    })
    // Keep resource pages valid after deleting the final item on a page.
    watch(() => variablePagination.value.page, page => {
      variablePage.value = page
    })
    // Keep the requested page valid after deleting tasks from the final page.
    watch(() => taskPagination.value.page, page => {
      taskPage.value = page
    })

    async function showVariableOnItsPage(variable) {
      props.editor.variableSearch.value = ''
      await nextTick()
      const index = variableList.value.indexOf(variable)
      if (index >= 0) variablePage.value = Math.floor(index / VARIABLE_RESOURCE_PAGE_SIZE) + 1
    }

    async function addVariableDefinition() {
      const variable = props.editor.createVar()
      variableList.value.push(variable)
      await showVariableOnItsPage(variable)
    }

    async function duplicateVariableDefinition(variable) {
      props.editor.duplicateVar(variable)
      const clone = variableList.value[variableList.value.indexOf(variable) + 1]
      if (clone) await showVariableOnItsPage(clone)
    }

    async function addDependentVariable(parent, eqValue = undefined) {
      const previousLength = variableList.value.length
      props.editor.handleAddDependentVar(parent, eqValue)
      if (variableList.value.length === previousLength) return
      const child = variableList.value[variableList.value.indexOf(parent) + 1]
      if (child) await showVariableOnItsPage(child)
    }

    function toggleAllVariableAdvanced() {
      const expanded = !allVariablesExpanded.value
      variableList.value.forEach(item => {
        item._showAdvanced = expanded
      })
    }

    async function addTaskDefinition() {
      taskList.value.push(props.editor.createTask())
      taskSearch.value = ''
      await nextTick()
      taskPage.value = Math.ceil(taskList.value.length / TASK_RESOURCE_PAGE_SIZE)
    }

    // Resource dialogs operate on the same unsaved template draft as the workflow workbench.
    return {
      ...props.editor,
      variablePage,
      variablePagination,
      allVariablesExpanded,
      taskSearch,
      taskPage,
      taskPagination,
      addVariableDefinition,
      duplicateVariableDefinition,
      addDependentVariable,
      toggleAllVariableAdvanced,
      addTaskDefinition,
    }
  },
}
</script>

<template>
  <n-modal
    v-model:show="settingsDialogVisible"
    preset="card"
    class="template-resource-dialog template-settings-dialog"
    title="模板设置"
    :bordered="false"
    :mask-closable="false"
  >
    <div class="resource-dialog-scroll">
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
          <n-input
            v-model:value="localData.d"
            type="textarea"
            placeholder="模板的功能描述、使用场景、注意事项"
            :rows="5"
          />
        </n-form-item>
      </n-form>
    </div>
    <template #footer>
      <n-space justify="end">
        <n-button type="primary" @click="closeSettingsDialog">完成</n-button>
      </n-space>
    </template>
  </n-modal>

  <n-modal
    v-model:show="variableDialogVisible"
    preset="card"
    class="template-resource-dialog"
    title="参数管理"
    :bordered="false"
    :mask-closable="false"
  >
    <div class="resource-dialog-layout">
      <div class="resource-dialog-toolbar">
        <n-input
          v-model:value="variableSearch"
          clearable
          placeholder="搜索参数键名 / 名称 / 说明 / 类型"
          class="resource-dialog-search"
        />
        <n-space>
          <n-button :disabled="!varsList.length" @click="toggleAllVariableAdvanced">
            {{ allVariablesExpanded ? '收起高级' : '展开高级' }}
          </n-button>
          <n-button type="primary" @click="addVariableDefinition">添加参数</n-button>
        </n-space>
      </div>

      <n-alert v-if="!varsList.length" type="default" :show-icon="false">
        还没有参数。创建后即可在任务流的参数绑定中直接选择。
      </n-alert>
      <n-alert v-else-if="!variablePagination.options.length" type="default" :show-icon="false">
        没有匹配的参数。
      </n-alert>

      <div v-if="variablePagination.options.length" class="resource-dialog-list-scroll">
        <div class="variable-editor-list">
          <template v-for="value in variablePagination.options" :key="value">
            <div
              class="editor-card editor-card-full"
              :class="{ 'is-dependent': value.if?.k }"
            >
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
                  <n-button size="small" quaternary @click="duplicateVariableDefinition(value)">复制</n-button>
                  <n-button size="small" quaternary @click="value._showAdvanced = !value._showAdvanced">
                    {{ value._showAdvanced ? '收起高级' : '展开高级' }}
                  </n-button>
                  <n-popconfirm @positive-click="removeVariableDefinition(value)">
                    <template #trigger>
                      <n-button size="small" type="error" quaternary>删除</n-button>
                    </template>
                    删除后将清理 {{ getVariableReferenceCount(value) }} 处关联引用，是否继续？
                  </n-popconfirm>
                </n-space>
              </div>

              <div class="form-grid cols-3 compact-grid">
                <n-input :value="value._key" placeholder="参数键名 (英文)" @update:value="key => setVariableKey(value, key)" />
                <n-input v-model:value="value.t" placeholder="显示名称" />
                <n-select
                  v-model:value="value.tp"
                  :options="tpOptions"
                  @update:value="handleVariableTypeChange(value)"
                />
              </div>

              <n-collapse :expanded-names="value._showAdvanced ? ['advanced'] : []" class="ghost-collapse">
                <n-collapse-item name="advanced">
                  <template #header><span></span></template>
                  <div class="advanced-panel">
                    <div v-if="value.if?.k" class="sub-panel dependent-variable-panel">
                      <div class="sub-panel-title dependent-variable-title">
                        <span>受控关联参数</span>
                        <n-button size="small" type="error" quaternary @click="value.if = null">取消关联</n-button>
                      </div>
                      <n-text depth="3" class="dependent-variable-copy">
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

                    <div v-if="value.tp === 'int' || value.tp === 'num'" class="form-grid cols-3 compact-grid">
                      <n-input-number v-model:value="value.def" placeholder="默认值" style="width: 100%;" />
                      <n-input-number v-model:value="value.min" placeholder="最小值" style="width: 100%;" />
                      <n-input-number v-model:value="value.max" placeholder="最大值" style="width: 100%;" />
                    </div>
                    <div v-else-if="value.tp === 'str'" class="form-grid cols-2 compact-grid">
                      <n-input v-model:value="value.def" placeholder="默认值" />
                      <n-select v-model:value="value.ui" :options="strUiOptions" placeholder="输入方式" />
                    </div>
                    <div v-else-if="value.tp === 'bool'" class="inline-switch-field panel-block">
                      <n-switch v-model:value="value.def" />
                      <span>默认状态</span>
                    </div>
                    <div v-else-if="value.tp === 'json'" class="form-grid cols-1 compact-grid">
                      <n-input v-model:value="value.def" type="textarea" :rows="4" placeholder="JSON 默认值" />
                    </div>

                    <div v-if="value.tp === 'enum'" class="sub-panel">
                      <div class="sub-panel-title">枚举选项</div>
                      <n-dynamic-input v-model:value="value.oneOf" :on-create="createEnumOption" class="enum-options-dynamic-input">
                        <template #default="{ value: opt }">
                          <div class="child-card enum-option-card">
                            <div class="form-grid cols-2 compact-grid">
                              <n-input v-model:value="opt.v" placeholder="值 (value)" />
                              <n-input v-model:value="opt.t" placeholder="显示名称 (t)" />
                            </div>
                            <n-button size="small" dashed @click="addDependentVariable(value, opt.v)">
                              以此选项作为条件添加关联参数
                            </n-button>
                          </div>
                        </template>
                      </n-dynamic-input>
                      <div class="form-grid cols-1 compact-grid enum-default-field">
                        <n-input v-model:value="value.def" placeholder="默认值，填写 oneOf 中的 v" />
                      </div>
                    </div>

                    <n-button v-if="value.tp === 'bool'" dashed @click="addDependentVariable(value, 'true')">
                      以此开关开启作为条件添加关联参数
                    </n-button>
                  </div>
                </n-collapse-item>
              </n-collapse>
            </div>
          </template>
        </div>
      </div>

      <div v-if="varsList.length" class="resource-dialog-pagination">
        <span>共 {{ variablePagination.total }} 项</span>
        <n-pagination
          v-model:page="variablePage"
          :page-count="variablePagination.pageCount"
          :page-slot="5"
          size="small"
        />
      </div>
    </div>
    <template #footer>
      <n-space justify="space-between" align="center">
        <n-text depth="3">参数变更会自动保存到模板</n-text>
        <n-button type="primary" @click="closeVariableDialog">完成</n-button>
      </n-space>
    </template>
  </n-modal>

  <n-modal
    v-model:show="taskDialogVisible"
    preset="card"
    class="template-resource-dialog"
    title="任务管理"
    :bordered="false"
    :mask-closable="false"
  >
    <div class="resource-dialog-layout">
      <div class="resource-dialog-toolbar">
        <n-input
          v-model:value="taskSearch"
          clearable
          placeholder="搜索任务 Key / 名称 / Blockly 函数"
          class="resource-dialog-search"
        />
        <n-space>
          <n-button @click="refreshProcedureDefinitions">刷新函数列表</n-button>
          <n-button type="primary" @click="addTaskDefinition">添加任务</n-button>
        </n-space>
      </div>

      <n-alert v-if="!procedureOptions.length" type="warning" :show-icon="false">
        当前 Blockly 工作区没有可绑定的函数。请先创建至少一个参数为 args 的有返回函数或无返回函数。
      </n-alert>

      <n-alert v-if="!localData.tasks.length" type="default" :show-icon="false">
        还没有任务。添加后即可绑定 Blockly 函数和模板参数。
      </n-alert>
      <n-alert v-else-if="!taskPagination.options.length" type="default" :show-icon="false">
        没有匹配的任务。
      </n-alert>

      <div v-if="taskPagination.options.length" class="resource-dialog-list-scroll">
        <div class="task-editor-list">
          <div v-for="value in taskPagination.options" :key="value" class="editor-card task-editor-card">
            <div class="task-editor-grid">
              <n-input :value="value.k" placeholder="任务 Key，例如 battle" @update:value="key => setTaskKey(value, key)" />
              <n-input v-model:value="value.t" placeholder="任务名称，例如 执行战斗" />
              <n-select
                v-model:value="value.fn"
                :options="procedureOptions"
                clearable
                filterable
                placeholder="选择 Blockly 函数"
                @update:value="handleTaskFunctionChange(value)"
              />
              <n-popconfirm @positive-click="removeTaskDefinition(value)">
                <template #trigger>
                  <n-button size="small" type="error" quaternary>删除</n-button>
                </template>
                删除后将移除任务流中的 {{ getTaskReferenceCount(value) }} 个任务实例，是否继续？
              </n-popconfirm>
            </div>
            <div class="field-block">
              <div class="field-label">任务参数</div>
              <div class="picker-summary-row">
                <div class="picker-summary-text">已选择 {{ value.args?.length || 0 }} 项</div>
                <n-button size="small" @click="openTaskVarPicker(value)">选择参数</n-button>
              </div>
              <div v-if="value.args?.length" class="task-selected-tags">
                <n-tag v-for="arg in value.args" :key="arg" size="small" type="info" round>{{ arg }}</n-tag>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="localData.tasks.length" class="resource-dialog-pagination">
        <span>共 {{ taskPagination.total }} 项</span>
        <n-pagination
          v-model:page="taskPage"
          :page-count="taskPagination.pageCount"
          :page-slot="5"
          size="small"
        />
      </div>
    </div>
    <template #footer>
      <n-space justify="space-between" align="center">
        <n-text depth="3">任务变更会自动保存到模板</n-text>
        <n-button type="primary" @click="closeTaskDialog">完成</n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<style scoped src="./templateResourceDialogs.css"></style>
