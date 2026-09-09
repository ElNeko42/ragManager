<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import BaseButton from './BaseButton.vue'
import BaseModal from './BaseModal.vue'

withDefaults(
  defineProps<{
    title: string
    question: string
    consequences?: string[]
    confirmLabel?: string
    busy?: boolean
  }>(),
  { consequences: () => [], confirmLabel: '', busy: false }
)
const emit = defineEmits<{ confirm: []; cancel: [] }>()

const { t } = useI18n()
</script>

<template>
  <BaseModal :title="title" @close="emit('cancel')">
    <div class="ask">
      <p class="question">{{ question }}</p>

      <ul v-if="consequences.length" class="consequences">
        <li v-for="line in consequences" :key="line">{{ line }}</li>
      </ul>

      <p class="final">{{ t('common.cannotBeUndone') }}</p>

      <div class="choices">
        <BaseButton variant="quiet" :disabled="busy" @click="emit('cancel')">
          {{ t('drive.cancel') }}
        </BaseButton>
        <button type="button" class="danger" :disabled="busy" @click="emit('confirm')">
          {{ confirmLabel || t('common.confirmDelete') }}
        </button>
      </div>
    </div>
  </BaseModal>
</template>

<style scoped>
.ask {
  display: flex;
  flex-direction: column;
  gap: var(--rm-space-3);
}

.question {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.35;
}

.consequences {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 0;
  padding: var(--rm-space-3) var(--rm-space-3) var(--rm-space-3) 30px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 12px;
  background: var(--rm-panel2);
  font-size: 13px;
}

.final {
  margin: 0;
  font-family: var(--rm-font-mono);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--rm-muted);
}

.choices {
  display: flex;
  justify-content: flex-end;
  gap: var(--rm-space-2);
  padding-top: var(--rm-space-2);
  border-top: var(--rm-border-width) dotted var(--rm-line);
}

.danger {
  padding: 10px var(--rm-space-4);
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 999px;
  background: var(--rm-pink);
  color: #17131f;
  font-family: var(--rm-font-display);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 3px 3px 0 var(--rm-shadow);
}

.danger:hover:not(:disabled) {
  transform: translate(-1px, -1px);
  box-shadow: 4px 4px 0 var(--rm-shadow);
}

.danger:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
