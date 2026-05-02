<script setup>
import { NButton, NInput, NInputNumber, NSelect, NCheckbox, NText, NCard, NGrid, NGridItem } from 'naive-ui'

const props = defineProps({
  form: { type: Object, default: null },
  formValues: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['update:formValues', 'open-field-picker'])

const fields = props.form?.fields || []

function updateField(key, value) {
  emit('update:formValues', {
    ...props.formValues,
    [key]: value,
  })
}
</script>

<template>
  <div style="display: flex; flex-direction: column; gap: 16px; height: 100%;">
    <n-card v-if="form?.intro" size="small" style="background: var(--n-color-embedded);">
      <n-text strong style="display: block; margin-bottom: 4px;">{{ form.intro.title }}</n-text>
      <n-text depth="3">{{ form.intro.text }}</n-text>
    </n-card>

    <n-grid :cols="2" :x-gap="16" :y-gap="16">
      <n-grid-item v-for="field in fields" :key="field.key" :span="field.type === 'textarea' ? 2 : 1">
        <template v-if="field.type === 'select'">
          <n-text strong>{{ field.label }}</n-text>
          <n-select :value="formValues[field.key]" :options="field.options || []" style="margin-top: 8px;" @update:value="value => updateField(field.key, value)" />
        </template>

        <template v-else-if="field.type === 'number'">
          <n-text strong>{{ field.label }}</n-text>
          <n-input-number :value="formValues[field.key]" style="margin-top: 8px; width: 100%;" @update:value="value => updateField(field.key, value)" />
        </template>

        <template v-else-if="field.type === 'checkbox'">
          <div style="display: flex; align-items: center; gap: 8px; margin-top: 8px;">
            <n-checkbox :checked="Boolean(formValues[field.key])" @update:checked="value => updateField(field.key, value)" />
            <n-text strong>{{ field.label }}</n-text>
          </div>
        </template>

        <template v-else>
          <n-text strong>{{ field.label }}</n-text>
          <n-text v-if="field.description" depth="3" style="display: block; margin-top: 4px; font-size: 12px;">{{ field.description }}</n-text>

          <div v-if="field.picker" style="display: flex; gap: 8px; margin-top: 8px; align-items: center;">
            <n-input :value="formValues[field.key] ?? ''" readonly />
            <n-button @click="emit('open-field-picker', field)">选择</n-button>
          </div>

          <n-input
            v-else-if="field.type === 'textarea'"
            :value="formValues[field.key]"
            type="textarea"
            :rows="field.rows || 4"
            style="margin-top: 8px;"
            @update:value="value => updateField(field.key, value)"
          />
          <n-input
            v-else
            :value="formValues[field.key]"
            :placeholder="field.placeholder || ''"
            style="margin-top: 8px;"
            @update:value="value => updateField(field.key, value)"
          />
        </template>
      </n-grid-item>
    </n-grid>
  </div>
</template>
