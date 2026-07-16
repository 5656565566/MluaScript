<script setup>
import { computed } from 'vue'
import { state } from '../store'
import BlocklyView from './BlocklyView.vue'
import DeviceManagerView from './DeviceManagerView.vue'
import DeviceView from './DeviceView.vue'
import RunLogsView from './RunLogsView.vue'
import TaskManagerView from './TaskManagerView.vue'
import TemplateRunnerView from './TemplateRunnerView.vue'

const workspaceViews = {
  blockly: BlocklyView,
  'task-manager': TaskManagerView,
  'template-runner': TemplateRunnerView,
  device: DeviceView,
  'device-manager': DeviceManagerView,
  'run-logs': RunLogsView,
}

const activeComponent = computed(() => workspaceViews[state.activeView.value] || BlocklyView)
</script>

<template>
  <component :is="activeComponent" />
</template>
