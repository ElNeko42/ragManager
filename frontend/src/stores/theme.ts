import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export type Theme = 'light' | 'dark'
export type ThemeChoice = Theme | 'system'

const STORAGE_KEY = 'ragmanager.theme'
const DARK_QUERY = '(prefers-color-scheme: dark)'

/**
 * Works out which theme to open the panel in.
 *
 * Prefers the one chosen on this device and otherwise follows the operating
 * system, since a panel that ignores a dark desktop is a panel that glares.
 */
function resolveInitialChoice(): ThemeChoice {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored === 'light' || stored === 'dark' || stored === 'system') {
      return stored
    }
  } catch {
    // A browser that refuses storage is treated as having no choice stored.
  }
  return 'system'
}

export const useThemeStore = defineStore('theme', () => {
  const choice = ref<ThemeChoice>(resolveInitialChoice())
  const systemIsDark = ref(window.matchMedia(DARK_QUERY).matches)

  window.matchMedia(DARK_QUERY).addEventListener('change', (event) => {
    systemIsDark.value = event.matches
  })

  /**
   * The theme actually on screen, which is the desktop's while following it.
   */
  const theme = computed<Theme>(() => {
    if (choice.value === 'system') {
      return systemIsDark.value ? 'dark' : 'light'
    }
    return choice.value
  })

  /**
   * Writes the choice onto the document and remembers it on this device.
   *
   * The attribute is what the stylesheet reads, so setting it is what actually
   * changes the colours. Following the desktop means writing no attribute at
   * all: the stylesheet then answers the media query on its own, and keeps
   * answering it when the desktop changes at dusk.
   */
  function apply(): void {
    if (choice.value === 'system') {
      delete document.documentElement.dataset.theme
    } else {
      document.documentElement.dataset.theme = choice.value
    }
    try {
      window.localStorage.setItem(STORAGE_KEY, choice.value)
    } catch {
      return
    }
  }

  /**
   * Fixes the panel on one of the two themes and applies the result.
   */
  function choose(next: ThemeChoice): void {
    choice.value = next
    apply()
  }

  /**
   * Switches to the opposite of what is on screen right now.
   *
   * Following the desktop counts as a starting point rather than a state to
   * return to: the header switch is for someone who wants the other one now.
   */
  function toggle(): void {
    choose(theme.value === 'light' ? 'dark' : 'light')
  }

  return { choice, theme, apply, choose, toggle }
})
