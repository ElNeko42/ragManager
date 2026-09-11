<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import BaseSwitch from '../ui/BaseSwitch.vue'
import StatusBadge from './StatusBadge.vue'
import { formatBytes, formatExtension } from '../../api/format'
import { progressOf } from '../../stores/drive'
import type { Document } from '../../api/drive'

const props = defineProps<{ document: Document; selected: boolean }>()
const emit = defineEmits<{ select: []; active: [value: boolean] }>()

const { t } = useI18n()

const active = computed({
  get: () => props.document.is_agent_active,
  set: (value: boolean) => emit('active', value)
})
</script>

<template>
  <div :class="['row', { on: selected }]" @click="emit('select')">
    <span class="naming">
      <span class="ext" aria-hidden="true">{{ formatExtension(document.name) }}</span>
      <span class="text">
        <button type="button" class="name" @click="emit('select')">{{ document.name }}</button>
        <span class="size">{{ formatBytes(document.size_bytes) }}</span>
      </span>
    </span>
    <span @click.stop>
      <BaseSwitch v-if="document.is_indexable" v-model="active" :label="t('drive.switchLabel')" />
      <span v-else class="unreadable" :title="t('drive.unreadableHint')">{{ t('drive.unreadable') }}</span>
    </span>
    <StatusBadge :progress="progressOf(document)" />
  </div>
</template>

<style scoped>
.unreadable {
  font-size: 11px;
  color: var(--rm-muted);
  white-space: nowrap;
}

.row {
  display: grid;
  grid-template-columns: var(--rm-doc-cols, minmax(80px, 1fr) 96px 120px);
  gap: var(--rm-space-3);
  align-items: center;
  padding: 10px var(--rm-space-4);
  border-top: var(--rm-border-width) solid var(--rm-line);
  cursor: pointer;
}

.row:hover {
  background: var(--rm-panel2);
}

.on {
  background: var(--rm-panel2);
  box-shadow: inset 4px 0 0 var(--rm-pink);
}

.naming {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
}

.ext {
  flex: none;
  padding: 2px 6px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 6px;
  background: var(--rm-panel2);
  font-family: var(--rm-font-mono);
  font-size: 10px;
  font-weight: 700;
}

.text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.name {
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  overflow-wrap: anywhere;
  cursor: pointer;
}

.size {
  font-family: var(--rm-font-mono);
  font-size: 10px;
  color: var(--rm-muted);
}

@media (max-width: 600px) {
  .row {
    gap: var(--rm-space-2);
    padding: 10px var(--rm-space-3);
  }
}
</style>
