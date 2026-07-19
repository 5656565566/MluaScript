<script>
import { NAlert, NButton, NInput, NInputNumber, NModal, NSelect, NSpace, NSwitch, NText } from 'naive-ui'

export default {
  components: { NAlert, NButton, NInput, NInputNumber, NModal, NSelect, NSpace, NSwitch, NText },
  props: {
    editor: {
      type: Object,
      required: true,
    },
  },
  setup(props) {
    return { ...props.editor }
  },
}
</script>

<template>
  <n-modal
    v-model:show="pickerState.show"
    preset="card"
    class="template-picker-dialog"
    :title="pickerState.title"
    :bordered="false"
    :mask-closable="false"
  >
    <div class="picker-dialog-body">
      <n-alert v-if="pickerState.summary" type="info" :show-icon="false" class="picker-dialog-alert">
        {{ pickerState.summary }}
      </n-alert>
      <n-input
        v-model:value="pickerState.search"
        clearable
        placeholder="搜索键名 / 名称 / 来源"
        class="picker-dialog-search"
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
    class="template-step-arg-dialog"
    title="配置参数覆盖"
    :bordered="false"
    :mask-closable="false"
  >
    <div class="step-arg-editor-body">
      <n-alert type="info" :show-icon="false" class="step-arg-editor-alert">
        只勾选需要覆盖的任务参数；未勾选项继续使用任务自身的参数值。
      </n-alert>
      <div class="step-arg-editor-list">
        <div v-if="!stepArgEditorState.rows.length" class="picker-empty-text">当前任务没有可覆盖的参数</div>
        <div v-for="row in stepArgEditorState.rows" :key="row.key" class="step-arg-editor-row">
          <div class="step-arg-editor-enable">
            <input v-model="stepArgEditorState.selectedKeys" type="checkbox" :value="row.key" class="picker-option-checkbox" />
          </div>
          <div class="step-arg-editor-key">
            <div>{{ row.label }}</div>
            <n-text depth="3">{{ row.key }}</n-text>
          </div>
          <div class="step-arg-editor-inputs">
            <div class="step-arg-binding-grid">
              <n-select
                :value="row.binding.$bind"
                :options="bindingSourceOptions"
                :disabled="!stepArgEditorState.selectedKeys.includes(row.key)"
                @update:value="value => setStepArgEditorSource(row, value)"
              />
              <n-select
                v-if="row.binding.$bind === 'var'"
                v-model:value="row.binding.key"
                :options="stepArgSourceOptions.slice(1)"
                :disabled="!stepArgEditorState.selectedKeys.includes(row.key)"
                filterable
                clearable
                placeholder="选择模板参数"
              />
              <n-switch
                v-else-if="row.tp === 'bool'"
                v-model:value="row.binding.value"
                :disabled="!stepArgEditorState.selectedKeys.includes(row.key)"
              />
              <n-input-number
                v-else-if="row.tp === 'int'"
                v-model:value="row.binding.value"
                :disabled="!stepArgEditorState.selectedKeys.includes(row.key)"
                style="width: 100%;"
                placeholder="填写固定值"
              />
              <n-select
                v-else-if="row.tp === 'enum'"
                v-model:value="row.binding.value"
                :options="enumOptionsForKey(row.key)"
                :disabled="!stepArgEditorState.selectedKeys.includes(row.key)"
                clearable
                placeholder="选择固定值"
              />
              <n-input
                v-else
                v-model:value="row.binding.value"
                :disabled="!stepArgEditorState.selectedKeys.includes(row.key)"
                placeholder="填写固定值"
              />
            </div>
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

<style scoped src="./templateAuxiliaryDialogs.css"></style>
