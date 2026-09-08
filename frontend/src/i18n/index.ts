import { createI18n } from 'vue-i18n'

import en from './locales/en.json'
import es from './locales/es.json'

export const SUPPORTED_LOCALES = ['en', 'es'] as const
export type Locale = (typeof SUPPORTED_LOCALES)[number]

const STORAGE_KEY = 'ragmanager.locale'
const FALLBACK: Locale = 'en'

/**
 * Works out which language to open the panel in.
 *
 * Prefers the one chosen on this device, then the browser's own, and falls
 * back to English, which is the language the messages are written in.
 */
export function resolveInitialLocale(): Locale {
  const stored = readStoredLocale()
  if (stored) {
    return stored
  }
  const preferred = navigator.languages ?? [navigator.language]
  for (const candidate of preferred) {
    const base = candidate.split('-')[0]
    if (isSupported(base)) {
      return base
    }
  }
  return FALLBACK
}

/**
 * Reports whether a language tag is one the panel has messages for.
 */
export function isSupported(value: string): value is Locale {
  return (SUPPORTED_LOCALES as readonly string[]).includes(value)
}

/**
 * Reads the language chosen on this device, or null when there is none.
 *
 * A browser that refuses access to storage is treated as having no choice
 * stored rather than as an error, since the panel works either way.
 */
function readStoredLocale(): Locale | null {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    return stored && isSupported(stored) ? stored : null
  } catch {
    return null
  }
}

/**
 * Remembers the chosen language on this device and applies it to the document.
 */
export function persistLocale(locale: Locale): void {
  document.documentElement.lang = locale
  try {
    window.localStorage.setItem(STORAGE_KEY, locale)
  } catch {
    return
  }
}

export const i18n = createI18n({
  legacy: false,
  locale: resolveInitialLocale(),
  fallbackLocale: FALLBACK,
  messages: { en, es }
})
