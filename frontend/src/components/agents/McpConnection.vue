<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import CopyBlock from '../ui/CopyBlock.vue'

const props = withDefaults(
  defineProps<{ url: string; token?: string; name?: string }>(),
  { token: '', name: 'ragmanager' }
)

const { t } = useI18n()

const PLACEHOLDER = 'rmg_your_token_here'

const secret = computed(() => props.token || PLACEHOLDER)

const serverName = computed(
  () => props.name.toLowerCase().replace(/[^a-z0-9-]+/g, '-').replace(/^-|-$/g, '') || 'ragmanager'
)

const command = computed(
  () =>
    `claude mcp add --transport http ${serverName.value} ${props.url} \\\n` +
    `  --header "Authorization: Bearer ${secret.value}"`
)

const configuration = computed(() =>
  JSON.stringify(
    {
      mcpServers: {
        [serverName.value]: {
          type: 'http',
          url: props.url,
          headers: { Authorization: `Bearer ${secret.value}` }
        }
      }
    },
    null,
    2
  )
)

const check = computed(
  () =>
    `curl -s -X POST ${props.url} \\\n` +
    `  -H "Authorization: Bearer ${secret.value}" \\\n` +
    `  -H "Content-Type: application/json" \\\n` +
    `  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'`
)
</script>

<template>
  <div class="connection">
    <p class="lead">{{ t('agents.connectLead') }}</p>
    <p v-if="!token" class="placeholder">{{ t('agents.connectPlaceholder') }}</p>

    <CopyBlock :label="t('agents.connectCli')" :code="command" />
    <CopyBlock :label="t('agents.connectFile')" :code="configuration" />
    <CopyBlock :label="t('agents.connectCheck')" :code="check" />
  </div>
</template>

<style scoped>
.connection {
  display: flex;
  flex-direction: column;
  gap: var(--rm-space-3);
}

.lead,
.placeholder {
  margin: 0;
  font-size: 13px;
  color: var(--rm-muted);
}

.placeholder {
  color: var(--rm-warn, var(--rm-muted));
}
</style>
