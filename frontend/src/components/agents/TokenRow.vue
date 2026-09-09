<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import BaseBadge from '../ui/BaseBadge.vue'
import { formatDate } from '../../api/format'
import type { AgentToken } from '../../api/agents'

const props = defineProps<{ token: AgentToken }>()
const emit = defineEmits<{ revoke: [] }>()

const { t } = useI18n()

const state = computed(() => {
  if (props.token.revoked_at) {
    return 'revoked' as const
  }
  return props.token.is_active ? ('active' as const) : ('expired' as const)
})

const meta = computed(() => {
  if (props.token.revoked_at) {
    return t('agents.revokedOn', { date: formatDate(props.token.revoked_at) })
  }
  if (props.token.expires_at) {
    return t('agents.expiresOn', { date: formatDate(props.token.expires_at) })
  }
  return t('agents.noExpiry')
})
</script>

<template>
  <div class="row">
    <span class="prefix">{{ token.token_prefix }}…</span>
    <span class="meta">{{ meta }}</span>
    <BaseBadge :tone="state === 'active' ? 'positive' : 'negative'">
      {{ t(`agents.state.${state}`) }}
    </BaseBadge>
    <button v-if="state === 'active'" type="button" class="revoke" @click="emit('revoke')">
      {{ t('agents.revoke') }}
    </button>
  </div>
</template>

<style scoped>
.row {
  display: flex;
  align-items: center;
  gap: var(--rm-space-2);
  flex-wrap: wrap;
  padding: var(--rm-space-2) 10px;
  border: var(--rm-border-width) solid var(--rm-line);
  border-radius: 10px;
  background: var(--rm-panel2);
}

.prefix {
  font-family: var(--rm-font-mono);
  font-size: 12px;
  font-weight: 700;
}

.meta {
  margin-right: auto;
  font-family: var(--rm-font-mono);
  font-size: 10.5px;
  color: var(--rm-muted);
}

.revoke {
  padding: 3px 9px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 999px;
  background: transparent;
  color: var(--rm-neg);
  font-size: 11.5px;
  font-weight: 700;
  cursor: pointer;
}

.revoke:hover {
  background: var(--rm-neg-soft);
}
</style>
