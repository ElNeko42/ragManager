<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import BaseAlert from '../ui/BaseAlert.vue'
import BaseButton from '../ui/BaseButton.vue'
import BaseIcon from '../ui/BaseIcon.vue'
import McpConnection from './McpConnection.vue'

const props = defineProps<{ token: string; agentName: string; mcpUrl: string }>()
const emit = defineEmits<{ done: [] }>()

const { t } = useI18n()
const copied = ref(false)
const failed = ref(false)

/**
 * Puts the token on the clipboard.
 *
 * A browser can refuse clipboard access, so a failure says so rather than
 * pretending it worked: the token is on screen exactly once and a silent
 * failure would cost the owner the only copy they will ever see.
 */
async function copy(): Promise<void> {
  failed.value = false
  try {
    await navigator.clipboard.writeText(props.token)
    copied.value = true
  } catch {
    failed.value = true
  }
}
</script>

<template>
  <div class="reveal">
    <BaseAlert tone="negative">{{ t('agents.onlyOnce') }}</BaseAlert>

    <p class="who">{{ t('agents.tokenFor', { name: agentName }) }}</p>

    <output class="token">{{ token }}</output>

    <div class="row">
      <BaseButton variant="primary" @click="copy">
        <BaseIcon :name="copied ? 'check' : 'copy'" :size="17" />
        {{ copied ? t('agents.copied') : t('agents.copy') }}
      </BaseButton>
      <BaseButton @click="emit('done')">{{ t('agents.savedIt') }}</BaseButton>
    </div>

    <p v-if="failed" class="failed">{{ t('agents.copyFailed') }}</p>
    <p class="hint">{{ t('agents.tokenHint') }}</p>

    <details v-if="mcpUrl" class="connect" open>
      <summary>{{ t('agents.connectTitle') }}</summary>
      <McpConnection :url="mcpUrl" :token="token" :name="agentName" />
    </details>
  </div>
</template>

<style scoped>
.reveal {
  display: flex;
  flex-direction: column;
  gap: var(--rm-space-3);
}

.who {
  margin: 0;
  color: var(--rm-muted);
  font-size: 13px;
}

.token {
  display: block;
  padding: var(--rm-space-3);
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 12px;
  background: var(--rm-panel2);
  font-family: var(--rm-font-mono);
  font-size: 13px;
  overflow-wrap: anywhere;
  user-select: all;
}

.row {
  display: flex;
  gap: var(--rm-space-2);
  flex-wrap: wrap;
}

.failed {
  margin: 0;
  color: var(--rm-neg);
  font-size: 12.5px;
}

.connect {
  border-top: var(--rm-border-width) solid var(--rm-border);
  padding-top: var(--rm-space-3);
}

.connect summary {
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: var(--rm-space-3);
}

.hint {
  margin: 0;
  font-family: var(--rm-font-mono);
  font-size: 11px;
  color: var(--rm-muted);
}
</style>
