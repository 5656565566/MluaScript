<script>
import { NButton, NInput, NInputNumber, NSelect, NSpace, NSwitch, NTag, NText } from 'naive-ui'
import PaginatedSearchSelect from './PaginatedSearchSelect.vue'

export default {
  components: {
    NButton,
    NInput,
    NInputNumber,
    NSelect,
    NSpace,
    NSwitch,
    NTag,
    NText,
    PaginatedSearchSelect,
  },
  props: {
    editor: {
      type: Object,
      required: true,
    },
  },
  setup(props) {
    // Expose editor refs as top-level values so Vue can unwrap them in this focused view.
    return { ...props.editor }
  },
}
</script>

<template>
  <div class="flow-workbench-root">
    <div v-if="!selectedFlow" class="flow-empty-state">
      <div class="flow-empty-title">还没有任务流</div>
      <n-text depth="3">添加任务流后，将任务放入执行序列并绑定参数。</n-text>
      <n-button type="primary" @click="addFlow">添加第一个任务流</n-button>
    </div>

    <template v-else>
      <div class="flow-definition-bar">
        <n-input v-model:value="selectedFlow.k" placeholder="任务流 Key，例如 main" />
        <n-input v-model:value="selectedFlow.t" placeholder="任务流名称，例如 每日刷图" />
        <div class="flow-global-binding">
          <div class="flow-global-copy">
            <span>任务流参数</span>
            <n-text depth="3">{{ selectedFlow.g?.length || 0 }} 个可在运行时填写</n-text>
          </div>
          <n-button size="small" @click="openFlowGlobalPicker(selectedFlow)">选择参数</n-button>
        </div>
        <label class="flow-lock-setting">
          <span>
            <strong>锁定执行顺序</strong>
            <n-text depth="3">使用者不可调整顺序或关闭任务</n-text>
          </span>
          <n-switch v-model:value="selectedFlow.lockSteps" />
        </label>
      </div>

      <div v-if="selectedFlow.g?.length" class="flow-parameter-strip">
        <span class="flow-parameter-label">本流程可用</span>
        <n-tag v-for="globalArg in selectedFlow.g" :key="globalArg" size="small" type="success">
          {{ globalArg }}
        </n-tag>
      </div>

      <div class="flow-workbench">
        <aside class="flow-step-rail">
          <div class="flow-step-rail-header">
            <div>
              <div class="field-label">执行顺序</div>
              <n-text depth="3">{{ selectedFlow.steps?.length || 0 }} 个任务实例</n-text>
            </div>
            <n-button size="small" type="primary" @click="addStep">添加任务</n-button>
          </div>

          <div v-if="!selectedFlow.steps?.length" class="flow-step-empty">
            从任务定义中添加一个任务，随后即可绑定参数。
          </div>

          <div v-else class="flow-step-list">
            <button
              v-for="(step, index) in selectedFlow.steps"
              :key="`${step.k}-${index}`"
              type="button"
              class="flow-step-list-item"
              :class="{ 'is-active': index === selectedStepIndex }"
              :aria-pressed="index === selectedStepIndex"
              @click="selectStep(index)"
            >
              <span class="flow-step-order">{{ index + 1 }}</span>
              <span class="flow-step-list-copy">
                <strong>{{ step.k || '未命名任务' }}</strong>
                <span>{{ taskOptions.find(item => item.value === step.task)?.label || '尚未选择任务' }}</span>
              </span>
              <span
                class="flow-step-state"
                :class="{ 'is-complete': isStepBindingComplete(step) }"
                :title="isStepBindingComplete(step) ? '参数覆盖有效' : '参数覆盖有误'"
              ></span>
            </button>
          </div>
        </aside>

        <section v-if="selectedStep" class="flow-step-inspector">
          <div class="flow-step-inspector-header">
            <div>
              <div class="flow-step-inspector-title">配置任务实例</div>
              <n-text depth="3">任务定义可以复用，每个实例只保存参数覆盖与成功、失败去向。</n-text>
            </div>
            <n-space size="small">
              <n-button size="small" :disabled="selectedStepIndex === 0" @click="moveSelectedStep(-1)">上移</n-button>
              <n-button size="small" :disabled="selectedStepIndex >= selectedFlow.steps.length - 1" @click="moveSelectedStep(1)">下移</n-button>
              <n-button size="small" type="error" quaternary @click="removeSelectedStep">删除</n-button>
            </n-space>
          </div>

          <div class="flow-step-identity">
            <div>
              <div class="field-label">实例 ID</div>
              <n-input
                :value="selectedStep.k"
                placeholder="例如 battle_1"
                @update:value="setSelectedStepKey"
              />
            </div>
            <div>
              <div class="field-label-row">
                <div class="field-label">使用任务</div>
                <n-button text size="tiny" @click="openTaskDialog">管理任务</n-button>
              </div>
              <PaginatedSearchSelect
                :value="selectedStep.task"
                :options="taskOptions"
                clearable
                placeholder="选择任务定义"
                search-placeholder="搜索任务名称或 Key"
                @update:value="handleWorkbenchStepTaskChange"
              />
            </div>
          </div>

          <div class="flow-binding-section">
            <div class="flow-section-header">
              <div>
                <div class="flow-section-title">参数覆盖</div>
                <n-text depth="3">任务默认使用自身参数；这里只配置当前步骤需要改写的值。</n-text>
              </div>
              <n-space align="center">
                <n-tag :type="stepBindingStats.complete === stepBindingStats.total ? 'success' : 'warning'" size="small">
                  {{ stepBindingStats.total }} 项覆盖
                </n-tag>
                <n-button size="small" @click="openVariableDialog">管理参数</n-button>
                <n-button
                  size="small"
                  :disabled="!selectedStep.task"
                  @click="openStepArgsPicker(selectedFlow, selectedStep)"
                >
                  配置覆盖
                </n-button>
              </n-space>
            </div>

            <div v-if="!selectedStep.task" class="flow-inline-empty">先选择任务定义，再按需创建参数覆盖。</div>
            <div v-else-if="!stepBindingRows.length" class="flow-inline-empty">
              未设置参数覆盖，运行时使用任务自身参数。
            </div>
            <div v-else class="flow-binding-table">
              <div class="flow-binding-table-head">
                <span>任务参数</span>
                <span>取值方式</span>
                <span>绑定值</span>
              </div>
              <div v-for="row in stepBindingRows" :key="row.key" class="flow-binding-row">
                <div class="flow-binding-argument">
                  <strong>{{ row.label }}</strong>
                  <code>{{ row.key }}</code>
                </div>
                <n-select
                  :value="row.binding?.$bind || null"
                  :options="bindingSourceOptions"
                  placeholder="选择来源"
                  @update:value="value => setStepArgSource(row.key, value)"
                />
                <div class="flow-binding-value">
                  <n-select
                    v-if="row.binding?.$bind === 'var'"
                    :value="row.binding.key"
                    :options="stepArgSourceOptions.slice(1)"
                    filterable
                    placeholder="选择模板参数"
                    @update:value="value => setStepArgValue(row.key, value)"
                  />
                  <n-switch
                    v-else-if="row.binding?.$bind === 'literal' && row.tp === 'bool'"
                    :value="Boolean(row.binding.value)"
                    @update:value="value => setStepArgValue(row.key, value)"
                  />
                  <n-input-number
                    v-else-if="row.binding?.$bind === 'literal' && (row.tp === 'int' || row.tp === 'num')"
                    :value="row.binding.value"
                    style="width: 100%;"
                    @update:value="value => setStepArgValue(row.key, value)"
                  />
                  <n-select
                    v-else-if="row.binding?.$bind === 'literal' && row.tp === 'enum'"
                    :value="row.binding.value"
                    :options="enumOptionsForKey(row.key)"
                    clearable
                    placeholder="选择固定值"
                    @update:value="value => setStepArgValue(row.key, value)"
                  />
                  <n-input
                    v-else-if="row.binding?.$bind === 'literal' && row.tp === 'json'"
                    :value="row.binding.value"
                    type="textarea"
                    :rows="3"
                    placeholder="填写 JSON"
                    @update:value="value => setStepArgValue(row.key, value)"
                  />
                  <n-input
                    v-else-if="row.binding?.$bind === 'literal'"
                    :value="row.binding.value"
                    placeholder="填写固定值"
                    @update:value="value => setStepArgValue(row.key, value)"
                  />
                  <n-text v-else depth="3">请选择取值方式</n-text>
                </div>
              </div>
            </div>
          </div>

          <div class="flow-transition-section">
            <div class="flow-section-header">
              <div>
                <div class="flow-section-title">步骤转移</div>
                <n-text depth="3">成功时按顺序匹配任务流参数，首个命中的分支生效。</n-text>
              </div>
              <n-button size="small" :disabled="!flowVariableOptions.length || !workflowBranchTargetOptions.length" @click="addWorkflowBranch">
                添加参数分支
              </n-button>
            </div>

            <div v-if="selectedStep.successBranches?.length" class="flow-branch-list">
              <div v-for="(branch, branchIndex) in selectedStep.successBranches" :key="branchIndex" class="flow-branch-row">
                <span class="flow-branch-order">{{ branchIndex + 1 }}</span>
                <n-select
                  :value="branch.if?.k || null"
                  :options="flowVariableOptions"
                  filterable
                  placeholder="任务流参数"
                  @update:value="value => setWorkflowBranchParameter(branch, value)"
                />
                <n-select
                  :value="workflowBranchOperator(branch)"
                  :options="workflowBranchOperatorOptions(branch)"
                  :disabled="!branch.if?.k"
                  @update:value="value => setWorkflowBranchOperator(branch, value)"
                />
                <n-select
                  v-if="workflowBranchValueControl(branch) === 'select'"
                  :value="workflowBranchValue(branch)"
                  :options="workflowBranchValueOptions(branch)"
                  :multiple="workflowBranchValueMultiple(branch)"
                  :disabled="!branch.if?.k"
                  clearable
                  placeholder="条件值"
                  @update:value="value => setWorkflowBranchValue(branch, value)"
                />
                <n-input-number
                  v-else-if="workflowBranchValueControl(branch) === 'number'"
                  :value="workflowBranchValue(branch)"
                  :precision="workflowBranchValuePrecision(branch)"
                  :disabled="!branch.if?.k"
                  placeholder="条件值"
                  @update:value="value => setWorkflowBranchValue(branch, value)"
                />
                <n-input
                  v-else
                  :value="workflowBranchValue(branch)"
                  :disabled="!branch.if?.k"
                  :placeholder="workflowBranchValuePlaceholder(branch)"
                  @update:value="value => setWorkflowBranchValue(branch, value)"
                />
                <span class="flow-branch-arrow">跳转到</span>
                <n-select
                  v-model:value="branch.goto"
                  :options="workflowBranchTargetOptions"
                  filterable
                  placeholder="目标任务"
                />
                <n-button size="small" type="error" quaternary @click="removeWorkflowBranch(branchIndex)">删除</n-button>
              </div>
            </div>
            <div v-else class="flow-branch-empty">未配置参数分支。</div>

            <div class="flow-transition-grid">
              <div class="flow-transition-control">
                <div class="field-label">未命中分支时</div>
                <n-select
                  :value="selectedStep.onSuccess"
                  :options="onSuccessOptions"
                  @update:value="handleStepOnSuccessChange"
                />
                <n-select
                  v-if="selectedStep.onSuccess === 'goto'"
                  v-model:value="selectedStep.successGoto"
                  :options="gotoStepOptions"
                  filterable
                  clearable
                  placeholder="选择跳转任务"
                />
              </div>
              <div class="flow-transition-control">
                <div class="field-label">运行失败后</div>
                <n-select
                  :value="selectedStep.onFail"
                  :options="onFailOptions"
                  @update:value="handleStepOnFailChange"
                />
                <n-select
                  v-if="selectedStep.onFail === 'goto'"
                  v-model:value="selectedStep.goto"
                  :options="gotoStepOptions"
                  filterable
                  clearable
                  placeholder="选择跳转任务"
                />
              </div>
            </div>
          </div>
        </section>

        <section v-else class="flow-step-inspector flow-step-inspector-empty">
          <div class="flow-empty-title">选择或添加一个任务实例</div>
          <n-text depth="3">任务参数由任务自身负责，需要时可为当前步骤添加覆盖。</n-text>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped src="./templateFlowWorkbench.css"></style>
