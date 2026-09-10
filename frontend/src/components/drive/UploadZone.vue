<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import BaseIcon from '../ui/BaseIcon.vue'

const emit = defineEmits<{ files: [files: File[]] }>()
const { t } = useI18n()

const picker = ref<HTMLInputElement | null>(null)

/**
 * Hands over whatever was chosen in the file picker.
 *
 * The input is cleared afterwards so that picking the same file twice in a
 * row still counts as a second upload.
 */
function onPick(event: Event): void {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  if (files.length) {
    emit('files', files)
  }
  input.value = ''
}
</script>

<template>
  <div class="zone">
    <span class="text">
      <BaseIcon name="upload" :size="18" />
      {{ t('drive.dropHere') }}
    </span>
    <button type="button" class="pick" @click="picker?.click()">{{ t('drive.chooseFiles') }}</button>
    <input ref="picker" type="file" multiple hidden @change="onPick" />
  </div>
</template>

<style scoped>
/*
 * Dropping works over the whole page, so this is the sentence that says so and
 * the way in for anyone who would rather pick a file than drag one. It does no
 * dragging of its own: two listeners for one drop is one too many.
 */
.zone {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--rm-space-3);
  flex-wrap: wrap;
  padding: var(--rm-space-4);
  border: var(--rm-border-width) dashed var(--rm-border);
  border-radius: 14px;
  background: transparent;
}

.text {
  display: inline-flex;
  align-items: center;
  gap: var(--rm-space-2);
  font-family: var(--rm-font-mono);
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--rm-muted);
}

.pick {
  padding: 7px 12px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 999px;
  background: var(--rm-panel2);
  color: var(--rm-ink);
  font-size: 12.5px;
  font-weight: 700;
  cursor: pointer;
}

.pick:hover {
  background: var(--rm-pink);
  color: var(--rm-ink-on-bright);
}
</style>
