<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import BaseSegmented from '../ui/BaseSegmented.vue'
import { SUPPORTED_LOCALES, persistLocale } from '../../i18n'
import type { Locale } from '../../i18n'

const { t, locale } = useI18n()

const segments = SUPPORTED_LOCALES.map((code) => ({ value: code, label: code.toUpperCase() }))

const chosen = computed({
  get: () => locale.value,
  set: (value: string) => {
    locale.value = value
    persistLocale(value as Locale)
  }
})
</script>

<template>
  <BaseSegmented v-model="chosen" :segments="segments" :label="t('common.language')" />
</template>
