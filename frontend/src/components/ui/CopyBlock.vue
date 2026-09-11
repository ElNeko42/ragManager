<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import BaseButton from './BaseButton.vue'
import BaseIcon from './BaseIcon.vue'

const props = defineProps<{ label: string; code: string }>()

const { t } = useI18n()
const copied = ref(false)
const failed = ref(false)

/**
 * Puts the block on the clipboard.
 *
 * A browser can refuse clipboard access, and the whole point of the block is
 * that nobody should have to retype it, so a refusal says so instead of
 * leaving a button that looks like it worked. The text stays selectable either
 * way.
 */
async function copy(): Promise<void> {
  failed.value = false
  try {
    await navigator.clipboard.writeText(props.code)
    copied.value = true
    window.setTimeout(() => (copied.value = false), 2000)
  } catch {
    failed.value = true
  }
}
</script>

<template>
  <section class="block">
    <header class="head">
      <span class="label">{{ label }}</span>
      <BaseButton variant="quiet" @click="copy">
        <BaseIcon :name="copied ? 'check' : 'copy'" :size="15" />
        {{ copied ? t('agents.copied') : t('agents.copy') }}
      </BaseButton>
    </header>
    <pre class="code"><code>{{ code }}</code></pre>
    <p v-if="failed" class="failed">{{ t('agents.copyFailed') }}</p>
  </section>
</template>

<style scoped>
.block {
  display: flex;
  flex-direction: column;
  gap: var(--rm-space-2);
}

.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--rm-space-2);
}

.label {
  font-size: 12px;
  font-weight: 600;
  color: var(--rm-muted);
}

.code {
  margin: 0;
  padding: var(--rm-space-3);
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 12px;
  background: var(--rm-panel2);
  font-family: var(--rm-font-mono);
  font-size: 12px;
  line-height: 1.55;
  overflow-x: auto;
  white-space: pre;
  user-select: all;
}

.failed {
  margin: 0;
  color: var(--rm-neg);
  font-size: 12.5px;
}
</style>
