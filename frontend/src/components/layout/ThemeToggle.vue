<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useThemeStore } from '../../stores/theme'

const { t } = useI18n()
const themes = useThemeStore()

const label = computed(() => (themes.theme === 'light' ? t('theme.toDark') : t('theme.toLight')))
</script>

<template>
  <button type="button" class="toggle" @click="themes.toggle()">{{ label }}</button>
</template>

<style scoped>
.toggle {
  padding: 6px 12px;
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
  color: #17131f;
}
</style>
