import { createDiscreteApi, darkTheme } from 'naive-ui'
import { computed } from 'vue'
import { state } from './store'
import { buildNaiveThemeOverrides, isDarkTheme } from './app/theme'

export function setupNaiveDiscreteApi() {
  const themeRef = computed(() => {
    const isDark = isDarkTheme(state.appTheme.value, window)
    return isDark ? darkTheme : null
  })

  const { message, notification, dialog, loadingBar } = createDiscreteApi(
    ['message', 'dialog', 'notification', 'loadingBar'],
    {
      configProviderProps: computed(() => ({
        theme: themeRef.value,
        themeOverrides: buildNaiveThemeOverrides(
          state.colorTheme.value,
          state.customColor.value,
          isDarkTheme(state.appTheme.value, window),
        ),
      }))
    }
  )

  window.$message = message
  window.$notification = notification
  window.$dialog = dialog
  window.$loadingBar = loadingBar
}
