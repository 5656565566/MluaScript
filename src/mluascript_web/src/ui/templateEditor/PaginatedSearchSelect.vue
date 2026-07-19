<script>
import { computed, nextTick, ref, watch } from 'vue'
import { ChevronDown, SearchOutline } from '@vicons/ionicons5'
import { NButton, NIcon, NInput, NPagination, NPopover } from 'naive-ui'
import {
  DEFAULT_SELECT_PAGE_SIZE,
  filterSelectOptions,
  paginateSelectOptions,
} from './paginatedSelect.js'

export default {
  components: {
    ChevronDown,
    NButton,
    NIcon,
    NInput,
    NPagination,
    NPopover,
    SearchOutline,
  },
  inheritAttrs: false,
  props: {
    value: {
      type: [String, Number],
      default: null,
    },
    options: {
      type: Array,
      default: () => [],
    },
    pageSize: {
      type: Number,
      default: DEFAULT_SELECT_PAGE_SIZE,
    },
    placeholder: {
      type: String,
      default: '',
    },
    searchPlaceholder: {
      type: String,
      default: '搜索名称或 Key',
    },
    clearable: Boolean,
  },
  emits: ['update:value'],
  setup(props, { emit }) {
    const searchText = ref('')
    const requestedPage = ref(1)
    const panelVisible = ref(false)
    const searchInputRef = ref(null)
    const filteredOptions = computed(() => filterSelectOptions(props.options, searchText.value))
    const pagination = computed(() => paginateSelectOptions(
      filteredOptions.value,
      requestedPage.value,
      props.pageSize,
    ))
    const selectedOption = computed(() => {
      const matched = props.options.find(option => option.value === props.value)
      if (matched) return matched
      if (props.value === null || props.value === undefined || props.value === '') return null
      return { label: String(props.value), value: props.value }
    })

    // Keep the page valid when searching or when resource definitions are edited.
    watch(() => pagination.value.page, page => {
      requestedPage.value = page
    })

    function handleSearch(value) {
      searchText.value = value
      requestedPage.value = 1
    }

    async function handleShowChange(show) {
      panelVisible.value = show
      if (show) {
        searchText.value = ''
        requestedPage.value = 1
        await nextTick()
        searchInputRef.value?.focus()
      }
    }

    function selectOption(option) {
      emit('update:value', option.value)
      panelVisible.value = false
    }

    function clearSelection() {
      emit('update:value', null)
      panelVisible.value = false
    }

    return {
      searchText,
      requestedPage,
      panelVisible,
      searchInputRef,
      pagination,
      selectedOption,
      handleSearch,
      handleShowChange,
      selectOption,
      clearSelection,
    }
  },
}
</script>

<template>
  <n-popover
    :show="panelVisible"
    trigger="click"
    placement="bottom-start"
    width="trigger"
    :show-arrow="false"
    :content-style="{ padding: '0' }"
    @update:show="handleShowChange"
  >
    <template #trigger>
      <button
        v-bind="$attrs"
        type="button"
        class="paginated-select-trigger"
        aria-haspopup="listbox"
        :aria-expanded="panelVisible"
      >
        <span class="paginated-select-trigger-label" :class="{ 'is-placeholder': !selectedOption }">
          {{ selectedOption?.label || placeholder }}
        </span>
        <span class="paginated-select-trigger-action">
          <n-icon size="15"><SearchOutline /></n-icon>
          <span>搜索</span>
          <n-icon class="paginated-select-trigger-arrow" :class="{ 'is-open': panelVisible }" size="14">
            <ChevronDown />
          </n-icon>
        </span>
      </button>
    </template>

    <div class="paginated-select-panel">
      <div class="paginated-select-search-row">
        <n-input
          ref="searchInputRef"
          :value="searchText"
          :placeholder="searchPlaceholder"
          clearable
          @update:value="handleSearch"
        >
          <template #prefix><n-icon><SearchOutline /></n-icon></template>
        </n-input>
        <n-button
          v-if="clearable && selectedOption"
          size="small"
          quaternary
          @click="clearSelection"
        >
          清除
        </n-button>
      </div>

      <div v-if="pagination.options.length" class="paginated-select-options" role="listbox">
        <button
          v-for="option in pagination.options"
          :key="option.value"
          type="button"
          role="option"
          class="paginated-select-option"
          :class="{ 'is-selected': option.value === value }"
          :aria-selected="option.value === value"
          @click="selectOption(option)"
        >
          <span>{{ option.label }}</span>
          <span v-if="option.value === value" class="paginated-select-option-state">已选</span>
        </button>
      </div>
      <div v-else class="paginated-select-empty">没有匹配项</div>

      <div class="paginated-select-footer">
        <span>共 {{ pagination.total }} 项</span>
        <n-pagination
          v-model:page="requestedPage"
          :page-count="pagination.pageCount"
          size="small"
          simple
        />
      </div>
    </div>
  </n-popover>
</template>

<style scoped>
.paginated-select-trigger {
  width: 100%;
  min-height: 34px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 10px;
  border: 1px solid var(--n-border-color);
  border-radius: 3px;
  background: var(--n-color);
  color: var(--n-text-color);
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color 160ms var(--n-bezier), box-shadow 160ms var(--n-bezier);
}

.paginated-select-trigger:hover,
.paginated-select-trigger:focus-visible {
  border-color: var(--n-primary-color);
}

.paginated-select-trigger:focus-visible {
  outline: 0;
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--n-primary-color) 24%, transparent);
}

.paginated-select-trigger-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.paginated-select-trigger-label.is-placeholder {
  color: var(--n-placeholder-color);
}

.paginated-select-trigger-action {
  flex: none;
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--n-text-color-3);
  font-size: 12px;
}

.paginated-select-trigger-arrow {
  transition: transform 160ms var(--n-bezier);
}

.paginated-select-trigger-arrow.is-open {
  transform: rotate(180deg);
}

.paginated-select-panel {
  overflow: hidden;
  border-radius: 4px;
}

.paginated-select-search-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
}

.paginated-select-options {
  display: grid;
  max-height: 238px;
  overflow: auto;
  border-top: 1px solid var(--n-border-color);
  border-bottom: 1px solid var(--n-border-color);
}

.paginated-select-option {
  min-height: 34px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 7px 12px;
  border: 0;
  border-left: 2px solid transparent;
  background: transparent;
  color: var(--n-text-color);
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.paginated-select-option:hover,
.paginated-select-option:focus-visible {
  background: var(--n-color-hover);
}

.paginated-select-option:focus-visible {
  outline: 1px solid var(--n-primary-color);
  outline-offset: -1px;
}

.paginated-select-option.is-selected {
  border-left-color: var(--n-primary-color);
  background: var(--n-color-hover);
  color: var(--n-primary-color);
}

.paginated-select-option-state {
  flex: none;
  font-size: 11px;
}

.paginated-select-empty {
  padding: 28px 12px;
  border-top: 1px solid var(--n-border-color);
  border-bottom: 1px solid var(--n-border-color);
  color: var(--n-text-color-3);
  font-size: 12px;
  text-align: center;
}

.paginated-select-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  color: var(--n-text-color-3);
  font-size: 12px;
}

.paginated-select-footer :deep(.n-pagination-quick-jumper .n-input__input-el) {
  text-align: center;
}
</style>
