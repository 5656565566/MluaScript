import { createDiscreteApi, darkTheme } from 'naive-ui'
import { computed } from 'vue'
import { state } from './store'

export function setupNaiveDiscreteApi() {
  const themeRef = computed(() => {
    const themeValue = state.appTheme.value
    const isDark = themeValue === 'dark' || (themeValue === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
    return isDark ? darkTheme : null
  })

  const { message, notification, dialog, loadingBar } = createDiscreteApi(
    ['message', 'dialog', 'notification', 'loadingBar'],
    {
      configProviderProps: computed(() => ({
        theme: themeRef.value
      }))
    }
  )

  window.$message = message
  window.$notification = notification
  window.$dialog = dialog
  window.$loadingBar = loadingBar
}
