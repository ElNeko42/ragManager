import { defineStore } from 'pinia'
import { ref } from 'vue'

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'ragmanager.theme'

/**
 * Works out which theme to open the panel in.
 *
 * Prefers the one chosen on this device, then the one the operating system
 * asks for, since a panel that ignores a dark desktop is a panel that glares.
 */
function resolveInitialTheme(): Theme {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored === 'light' || stored === 'dark') {
      return stored
    }
  } catch {
    // A browser that refuses storage is treated as having no choice stored.
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export const useThemeStore = defineStore('theme', () => {
  const theme = ref<Theme>(resolveInitialTheme())

  /**
   * Writes the theme onto the document and remembers it on this device.
   *
   * The attribute is what the stylesheet reads, so setting it is what actually
   * changes the colours; storage only decides what the next visit looks like.
   */
  function apply(): void {
    document.documentElement.dataset.theme = theme.value
    try {
      window.localStorage.setItem(STORAGE_KEY, theme.value)
    } catch {
      return
    }
  }

  /**
   * Switches between the two themes and applies the result.
   */
  function toggle(): void {
    theme.value = theme.value === 'light' ? 'dark' : 'light'
    apply()
  }

  return { theme, apply, toggle }
})
