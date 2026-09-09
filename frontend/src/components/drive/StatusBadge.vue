<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import BaseBadge from '../ui/BaseBadge.vue'
import type { Progress } from '../../stores/drive'

const props = defineProps<{ progress: Progress }>()
const { t } = useI18n()

const tone = computed(() => {
  if (props.progress === 'ready') {
    return 'positive' as const
  }
  if (props.progress === 'failed') {
    return 'negative' as const
  }
  if (props.progress === 'never') {
    return 'neutral' as const
  }
  return 'warning' as const
})

const busy = computed(() => props.progress === 'pending' || props.progress === 'processing')
</script>

<template>
  <BaseBadge :tone="tone">
    <span class="inner">
      <span v-if="busy" class="churn" aria-hidden="true" />
      {{ t(`drive.progress.${progress}`) }}
    </span>
  </BaseBadge>
</template>

<style scoped>
.inner {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.churn {
  width: 8px;
  height: 8px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: rm-spin 700ms linear infinite;
}
</style>
