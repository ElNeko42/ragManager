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
  <article :class="['card', { on: selected }]" @click="emit('select')">
    <div class="top">
      <span class="ext" aria-hidden="true">{{ formatExtension(document.name) }}</span>
      <span class="naming">
        <button type="button" class="open" @click="emit('select')">{{ document.name }}</button>
        <span class="size">{{ formatBytes(document.size_bytes) }}</span>
      </span>
    </div>
    <div class="foot">
      <span @click.stop>
        <BaseSwitch v-model="active" :label="t('drive.switchLabel')" />
      </span>
      <StatusBadge :progress="progressOf(document)" />
    </div>
  </article>
</template>

<style scoped>
.card {
  display: flex;
  flex-direction: column;
  gap: var(--rm-space-3);
  min-width: 0;
  padding: var(--rm-space-4);
  background: var(--rm-panel);
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 14px;
  box-shadow: 4px 4px 0 var(--rm-shadow);
  cursor: pointer;
  transition: transform 90ms ease, box-shadow 90ms ease;
}

.card:hover {
  transform: translate(-1px, -1px);
  box-shadow: 6px 6px 0 var(--rm-shadow);
}

.card.on {
  background: var(--rm-panel2);
  box-shadow: 6px 6px 0 var(--rm-pink);
}

.card.on:hover {
  box-shadow: 8px 8px 0 var(--rm-pink);
}

.top {
  display: flex;
  align-items: center;
  gap: var(--rm-space-3);
  min-width: 0;
}

.ext {
  display: grid;
  place-items: center;
  flex: none;
  width: 46px;
  height: 54px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 6px 12px 6px 6px;
  background: var(--rm-panel2);
  font-family: var(--rm-font-mono);
  font-size: 11px;
  font-weight: 700;
}

.naming {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.open {
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  font-size: 15.5px;
  font-weight: 700;
  line-height: 1.25;
  text-align: left;
  overflow-wrap: anywhere;
  cursor: pointer;
}

.size {
  font-family: var(--rm-font-mono);
  font-size: 11px;
  color: var(--rm-muted);
}

.foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--rm-space-2);
  padding-top: var(--rm-space-3);
  border-top: var(--rm-border-width) dotted var(--rm-line);
}
</style>
