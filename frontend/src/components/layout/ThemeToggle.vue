<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import BaseIcon from '../ui/BaseIcon.vue'
import { useThemeStore } from '../../stores/theme'

const { t } = useI18n()
const themes = useThemeStore()

const label = computed(() => (themes.theme === 'light' ? t('theme.toDark') : t('theme.toLight')))
</script>

<template>
  <button type="button" class="toggle" :title="label" :aria-label="label" @click="themes.toggle()">
    <BaseIcon :name="themes.theme === 'light' ? 'moon' : 'sun'" :size="16" />
    <span class="label">{{ label }}</span>
  </button>
</template>

<style scoped>
.toggle {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 7px 9px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 999px;
  background: var(--rm-panel2);
  color: var(--rm-ink);
  font-family: var(--rm-font-mono);
  font-size: 11px;
  letter-spacing: 0.1em;
  cursor: pointer;
}

.toggle:hover {
  background: var(--rm-amber);
  color: var(--rm-ink-on-bright);
}

/*
 * The mark carries this on its own, and the words it would otherwise spend are
 * what the six destinations need to stay on the bar's one line. The label is
 * still read out, and still shown as a tooltip.
 */
.label {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  overflow: hidden;
  white-space: nowrap;
  clip-path: inset(50%);
}
</style>
