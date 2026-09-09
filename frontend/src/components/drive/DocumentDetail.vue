<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import BaseAlert from '../ui/BaseAlert.vue'
import BaseButton from '../ui/BaseButton.vue'
import BaseInput from '../ui/BaseInput.vue'
import BaseSwitch from '../ui/BaseSwitch.vue'
import StatusBadge from './StatusBadge.vue'
import { contentUrl } from '../../api/drive'
import { formatBytes, formatDate } from '../../api/format'
import { progressOf } from '../../stores/drive'
import type { DocumentDetail } from '../../api/drive'

const props = defineProps<{ document: DocumentDetail; path: string; collection: string }>()
const emit = defineEmits<{
  active: [value: boolean]
  rename: [name: string]
  remove: []
}>()

const { t } = useI18n()

const renaming = ref(false)
const draft = ref(props.document.name)
const confirming = ref(false)

watch(
  () => props.document.document_id,
  () => {
    renaming.value = false
    confirming.value = false
    draft.value = props.document.name
  }
)

const progress = computed(() => progressOf(props.document))

const active = computed({
  get: () => props.document.is_agent_active,
  set: (value: boolean) => emit('active', value)
})

const facts = computed(() => [
  { key: t('drive.fact.type'), value: props.document.content_type },
  { key: t('drive.fact.size'), value: formatBytes(props.document.size_bytes) },
  { key: t('drive.fact.revision'), value: `r${props.document.revision}` },
  { key: t('drive.fact.chunks'), value: String(props.document.chunk_count) },
  { key: t('drive.fact.collection'), value: props.collection },
  { key: t('drive.fact.uploaded'), value: formatDate(props.document.created_at) },
  { key: t('drive.fact.updated'), value: formatDate(props.document.updated_at) }
])

/**
 * Applies the new name, unless it was left unchanged or empty.
 */
function commitRename(): void {
  const name = draft.value.trim()
  renaming.value = false
  if (name && name !== props.document.name) {
    emit('rename', name)
  } else {
    draft.value = props.document.name
  }
}
</script>

<template>
  <aside class="detail">
    <span class="eyebrow">{{ t('drive.detail') }}</span>

    <form v-if="renaming" class="rename" @submit.prevent="commitRename">
      <BaseInput id="rename" v-model="draft" :required="true" />
      <BaseButton type="submit" variant="primary">{{ t('drive.save') }}</BaseButton>
    </form>
    <h3 v-else>{{ document.name }}</h3>

    <p class="path">{{ path }}</p>

    <div class="gates">
      <div class="gate">
        <span class="labels">
          <strong>{{ t('drive.switchLabel') }}</strong>
          <span class="hint">{{ t('drive.switchHint') }}</span>
        </span>
        <BaseSwitch v-model="active" :label="t('drive.switchLabel')" />
      </div>

      <div class="rule" />

      <div class="gate">
        <span class="labels">
          <strong>{{ t('drive.statusLabel') }}</strong>
          <span class="hint">{{ t('drive.statusHint') }}</span>
        </span>
        <StatusBadge :progress="progress" />
      </div>

      <p class="note">{{ t(`drive.note.${progress}`) }}</p>

      <BaseAlert v-if="document.last_error && progress === 'failed'" tone="negative">
        {{ document.last_error }}
      </BaseAlert>
    </div>

    <dl class="facts">
      <div v-for="fact in facts" :key="fact.key">
        <dt>{{ fact.key }}</dt>
        <dd>{{ fact.value }}</dd>
      </div>
    </dl>

    <div class="actions">
      <a class="download" :href="contentUrl(document.document_id)" download>
        {{ t('drive.download') }}
      </a>
      <BaseButton @click="renaming = true">{{ t('drive.rename') }}</BaseButton>
    </div>

    <div class="danger">
      <BaseButton v-if="!confirming" variant="quiet" @click="confirming = true">
        {{ t('drive.delete') }}
      </BaseButton>
      <template v-else>
        <span class="ask">{{ t('drive.deleteAsk') }}</span>
        <button type="button" class="yes" @click="emit('remove')">{{ t('drive.deleteYes') }}</button>
        <BaseButton variant="quiet" @click="confirming = false">{{ t('drive.cancel') }}</BaseButton>
      </template>
    </div>
  </aside>
</template>

<style scoped>
.detail {
  display: flex;
  flex-direction: column;
  gap: var(--rm-space-3);
  min-width: 0;
  padding: 15px;
  background: var(--rm-panel);
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: var(--rm-radius);
  box-shadow: var(--rm-lift) var(--rm-lift) 0 var(--rm-shadow);
}

.eyebrow {
  font-family: var(--rm-font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--rm-muted);
}

h3 {
  font-size: 19px;
  overflow-wrap: anywhere;
}

.rename {
  display: flex;
  flex-direction: column;
  gap: var(--rm-space-2);
}

.path {
  margin: 0;
  font-family: var(--rm-font-mono);
  font-size: 11px;
  color: var(--rm-muted);
  overflow-wrap: anywhere;
}

.gates {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: var(--rm-space-3);
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 12px;
  background: var(--rm-panel2);
}

.gate {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.labels {
  display: flex;
  flex-direction: column;
}

.labels strong {
  font-size: 13px;
}

.hint {
  font-family: var(--rm-font-mono);
  font-size: 10px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--rm-muted);
}

.rule {
  height: var(--rm-border-width);
  background: var(--rm-line);
}

.note {
  margin: 0;
  font-size: 12px;
  color: var(--rm-muted);
}

.facts {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin: 0;
}

.facts div {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  padding-bottom: 6px;
  border-bottom: var(--rm-border-width) dotted var(--rm-line);
}

dt {
  font-family: var(--rm-font-mono);
  font-size: 10.5px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--rm-muted);
}

dd {
  margin: 0;
  font-size: 12.5px;
  text-align: right;
  overflow-wrap: anywhere;
}

.actions {
  display: flex;
  gap: var(--rm-space-2);
  flex-wrap: wrap;
}

.download {
  display: inline-flex;
  align-items: center;
  padding: 10px var(--rm-space-4);
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: var(--rm-radius-sm);
  background: var(--rm-cyan);
  color: #17131f;
  font-weight: 700;
  text-decoration: none;
  box-shadow: 4px 4px 0 var(--rm-shadow);
}

.download:hover {
  color: #17131f;
  transform: translate(2px, 2px);
  box-shadow: 2px 2px 0 var(--rm-shadow);
}

.danger {
  display: flex;
  align-items: center;
  gap: var(--rm-space-2);
  flex-wrap: wrap;
  padding-top: var(--rm-space-2);
  border-top: var(--rm-border-width) dotted var(--rm-line);
}

.ask {
  font-size: 12.5px;
  color: var(--rm-neg);
}

.yes {
  padding: 7px 12px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 999px;
  background: var(--rm-neg-soft);
  color: var(--rm-neg);
  font-weight: 700;
  font-size: 12.5px;
  cursor: pointer;
}
</style>
