<script setup>
import { computed, ref, watch } from 'vue'
import { state } from '../store'
import { closeModal } from '../modalStore'
import {
  getWorkspaceSharedVariableItems,
  getSharedVariableReferenceCount,
  renameSharedVariableInWorkspace,
  collectWorkspaceSharedVariableNames,
} from '../blockly/utils'
import { NInput, NButton, NSpace, NList, NListItem, NThing, NTag, NAlert, NEmpty, NText } from 'naive-ui'

const props = defineProps({
  modalId: {
    type: String,
    required: true,
  },
})

const draftName = ref('')
const errorMessage = ref('')
const currentEditName = ref('')
const blocklyEditor = computed(() => state.blocklyEditor.value)
const registryVersion = computed(() => state.sharedVariableRegistryVersion.value)

const sharedVariables = computed(() => {
  registryVersion.value
  return getWorkspaceSharedVariableItems(blocklyEditor.value).map((item) => ({
    ...item,
    referenceCount: getSharedVariableReferenceCount(item.name, blocklyEditor.value),
  }))
})

function resetEditor() {
  draftName.value = ''
  errorMessage.value = ''
  currentEditName.value = ''
}

watch(() => props.modalId, () => {
  resetEditor()
}, { immediate: true })

function normalizeName(value) {
  return String(value || '').trim()
}

function ensureUniqueName(name, excludeName = '') {
  const normalizedName = normalizeName(name)
  const excluded = normalizeName(excludeName)
  if (!normalizedName) {
    throw new Error('变量名不能为空')
  }
  const exists = collectWorkspaceSharedVariableNames(blocklyEditor.value)
    .concat(getWorkspaceSharedVariableItems(blocklyEditor.value).map((item) => item.name))
    .filter((item, index, array) => array.indexOf(item) === index)
    .some((item) => item === normalizedName && item !== excluded)
  if (exists) {
    throw new Error(`变量“${normalizedName}”已存在`)
  }
  return normalizedName
}

function handleCreate() {
  try {
    const nextName = ensureUniqueName(draftName.value)
    if (!state.userCreatedSharedVariables.value.includes(nextName)) {
      state.userCreatedSharedVariables.value.push(nextName)
    }
    state.sharedVariableRegistryVersion.value += 1
    draftName.value = ''
    errorMessage.value = ''
    currentEditName.value = nextName
  } catch (error) {
    errorMessage.value = error.message || '新建全局状态失败'
  }
}

function startRename(item) {
  currentEditName.value = item.name
  draftName.value = item.name
  errorMessage.value = ''
}

function confirmRename(item) {
  try {
    if (item.readonlyName) {
      throw new Error(`变量“${item.name}”不允许改名`)
    }
    const nextName = ensureUniqueName(draftName.value, item.name)
    const updated = renameSharedVariableInWorkspace(item.name, nextName, blocklyEditor.value)
    if (!updated && item.referenceCount > 0) {
      throw new Error(`变量“${item.name}”改名失败`)
    }

    const index = state.userCreatedSharedVariables.value.indexOf(item.name)
    if (index !== -1) {
      state.userCreatedSharedVariables.value.splice(index, 1)
    }
    if (!state.userCreatedSharedVariables.value.includes(nextName)) {
      state.userCreatedSharedVariables.value.push(nextName)
    }

    state.sharedVariableRegistryVersion.value += 1
    draftName.value = ''
    currentEditName.value = ''
    errorMessage.value = ''
  } catch (error) {
    errorMessage.value = error.message || '重命名失败'
  }
}

function cancelRename() {
  draftName.value = ''
  currentEditName.value = ''
  errorMessage.value = ''
}

function close() {
  closeModal(props.modalId)
}
</script>

<template>
  <div style="display: flex; flex-direction: column; gap: 12px; height: 100%;">
    <div style="display: flex; gap: 10px;">
      <n-input
        v-model:value="draftName"
        placeholder="输入新的全局状态名"
        @keyup.enter="currentEditName ? null : handleCreate()"
        style="flex: 1;"
      />
      <n-button type="primary" @click="handleCreate" :disabled="!!currentEditName">新建状态</n-button>
    </div>

    <n-alert v-if="errorMessage" type="error" :show-icon="false" style="margin-bottom: 8px;">
      {{ errorMessage }}
    </n-alert>

    <div style="flex: 1; overflow-y: auto; min-height: 0;">
      <n-list bordered hoverable style="background: transparent;">
        <n-empty v-if="sharedVariables.length === 0" description="暂无全局状态，可先新建一个或在块中通过选择器创建。" style="margin: 24px 0;" />

        <n-list-item v-for="item in sharedVariables" :key="item.name">
          <n-thing>
            <template #header>
              <n-space align="center">
                <template v-if="currentEditName === item.name">
                  <n-input
                    v-model:value="draftName"
                    @keyup.enter="confirmRename(item)"
                    style="min-width: 240px;"
                    size="small"
                  />
                </template>
                <template v-else>
                  <n-text strong>{{ item.label || item.name }}</n-text>
                </template>
                <n-tag size="small" type="info" round>{{ item.group }}</n-tag>
              </n-space>
            </template>
            <template #description>
              <n-space size="small" align="center" style="font-size: 12px;">
                <n-text depth="3">引用 {{ item.referenceCount }} 处</n-text>
                <n-text depth="3" v-if="item.description">· {{ item.description }}</n-text>
                <n-text depth="3" v-if="item.readonlyName">· 系统保留</n-text>
              </n-space>
            </template>
          </n-thing>

          <template #suffix>
            <n-space v-if="currentEditName === item.name">
              <n-button type="primary" size="small" @click="confirmRename(item)">保存</n-button>
              <n-button size="small" @click="cancelRename">取消</n-button>
            </n-space>
            <n-space v-else>
              <n-button size="small" @click="startRename(item)" :disabled="item.readonlyName">改名</n-button>
            </n-space>
          </template>
        </n-list-item>
      </n-list>
    </div>
  </div>
</template>
