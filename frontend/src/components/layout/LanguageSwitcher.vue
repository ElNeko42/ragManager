<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { SUPPORTED_LOCALES, persistLocale } from '../../i18n'
import type { Locale } from '../../i18n'

const { t, locale } = useI18n()

/**
 * Switches the panel to another language and remembers the choice.
 */
function choose(event: Event): void {
  const chosen = (event.target as HTMLSelectElement).value as Locale
  locale.value = chosen
  persistLocale(chosen)
}
</script>

<template>
  <label class="switcher">
    <span class="visually-hidden">{{ t('common.language') }}</span>
    <select :value="locale" @change="choose">
      <option v-for="code in SUPPORTED_LOCALES" :key="code" :value="code">
        {{ code.toUpperCase() }}
      </option>
    </select>
  </label>
</template>

<style scoped>
select {
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-small);
  background: var(--surface-raised);
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
</style>
