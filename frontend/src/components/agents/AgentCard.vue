<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import BaseButton from '../ui/BaseButton.vue'
import TokenRow from './TokenRow.vue'
import { formatDate } from '../../api/format'
import type { AgentRow } from '../../stores/agents'

const props = defineProps<{ row: AgentRow }>()
const emit = defineEmits<{
  issue: []
  revoke: [tokenId: string]
  remove: []
  simulate: []
}>()

const { t } = useI18n()
const confirming = ref(false)

const initials = computed(() => props.row.agent.name.slice(0, 2).toUpperCase())

const live = computed(() => props.row.tokens.filter((token) => token.is_active).length)

const rules = computed(() => {
  const allow = props.row.rules.filter((rule) => rule.effect === 'allow').length
  const deny = props.row.rules.length - allow
  return t('agents.rulesSummary', { allow, deny })
})
</script>

<template>
  <article class="card">
    <header class="head">
      <span class="mark" aria-hidden="true">{{ initials }}</span>
      <span class="naming">
        <strong>{{ row.agent.name }}</strong>
        <span class="created">{{ t('agents.created', { date: formatDate(row.agent.created_at) }) }}</span>
      </span>
    </header>

    <div class="tokens">
      <span class="eyebrow">{{ t('agents.tokens', { live }) }}</span>
      <TokenRow
        v-for="token in row.tokens"
        :key="token.token_id"
        :token="token"
        @revoke="emit('revoke', token.token_id)"
      />
      <p v-if="!row.tokens.length" class="none">{{ t('agents.noTokens') }}</p>
    </div>

    <div class="rules">
      <span class="eyebrow">{{ t('agents.rules') }}</span>
      <span class="summary">{{ rules }}</span>
    </div>

    <div class="actions">
      <BaseButton @click="emit('simulate')">{{ t('agents.simulate') }}</BaseButton>
      <BaseButton @click="emit('issue')">{{ t('agents.newToken') }}</BaseButton>
    </div>

    <div class="danger">
      <BaseButton v-if="!confirming" variant="quiet" @click="confirming = true">
        {{ t('agents.delete') }}
      </BaseButton>
      <template v-else>
        <span class="ask">{{ t('agents.deleteAsk') }}</span>
        <button type="button" class="yes" @click="emit('remove')">{{ t('agents.deleteYes') }}</button>
        <BaseButton variant="quiet" @click="confirming = false">{{ t('drive.cancel') }}</BaseButton>
      </template>
    </div>
  </article>
</template>

<style scoped>
.card {
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

.head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.mark {
  display: grid;
  place-items: center;
  flex: none;
  width: 36px;
  height: 36px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 10px;
  background: var(--rm-cyan);
  color: #17131f;
  font-family: var(--rm-font-display);
  font-weight: 700;
}

.naming {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.naming strong {
  font-family: var(--rm-font-display);
  font-size: 17px;
  overflow-wrap: anywhere;
}

.created {
  font-family: var(--rm-font-mono);
  font-size: 10.5px;
  color: var(--rm-muted);
}

.tokens {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.eyebrow {
  font-family: var(--rm-font-mono);
  font-size: 10.5px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--rm-muted);
}

.none {
  margin: 0;
  font-size: 12.5px;
  color: var(--rm-muted);
}

.rules {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  padding-top: 9px;
  border-top: var(--rm-border-width) dotted var(--rm-line);
}

.summary {
  font-size: 12.5px;
  text-align: right;
}

.actions {
  display: flex;
  gap: var(--rm-space-2);
  flex-wrap: wrap;
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
