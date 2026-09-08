<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import AppShell from '../components/layout/AppShell.vue'
import BaseAlert from '../components/ui/BaseAlert.vue'
import BaseBadge from '../components/ui/BaseBadge.vue'
import BaseButton from '../components/ui/BaseButton.vue'
import BaseCard from '../components/ui/BaseCard.vue'
import BaseSpinner from '../components/ui/BaseSpinner.vue'
import { readHealth } from '../api/health'
import type { HealthReport } from '../api/health'

const { t, te } = useI18n()

const report = ref<HealthReport | null>(null)
const loading = ref(false)
const failed = ref(false)

/**
 * Reads the health report and keeps it for rendering.
 */
async function load(): Promise<void> {
  loading.value = true
  failed.value = false
  try {
    report.value = await readHealth()
  } catch {
    report.value = null
    failed.value = true
  } finally {
    loading.value = false
  }
}

/**
 * Returns the readable name of a service, or its own key when untranslated.
 *
 * A service added later shows up under its identifier rather than as a missing
 * translation, so the report stays useful before the wording catches up.
 */
function serviceName(key: string): string {
  const path = `status.services.${key}`
  return te(path) ? t(path) : key
}

onMounted(load)
</script>

<template>
  <AppShell>
    <BaseCard :title="t('status.title')" :subtitle="t('status.subtitle')">
      <template #actions>
        <BaseButton :disabled="loading" @click="load">{{ t('status.refresh') }}</BaseButton>
      </template>

      <BaseSpinner v-if="loading && !report" :label="t('common.loading')" />
      <BaseAlert v-else-if="failed" tone="negative">{{ t('common.unexpectedError') }}</BaseAlert>
      <template v-else-if="report">
        <BaseAlert :tone="report.healthy ? 'positive' : 'negative'">
          {{ report.healthy ? t('status.allHealthy') : t('status.someUnhealthy') }}
        </BaseAlert>
        <ul class="services">
          <li v-for="(service, key) in report.services" :key="key">
            <span class="name">{{ serviceName(String(key)) }}</span>
            <BaseBadge :tone="service.healthy ? 'positive' : 'negative'">
              {{ service.healthy ? t('status.healthy') : t('status.unhealthy') }}
            </BaseBadge>
            <span v-if="service.detail" class="detail">{{ service.detail }}</span>
          </li>
        </ul>
      </template>
    </BaseCard>
  </AppShell>
</template>

<style scoped>
.services {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

li {
  display: grid;
  grid-template-columns: 200px auto 1fr;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--border);
}

li:last-child {
  border-bottom: none;
}

.name {
  font-weight: 500;
}

.detail {
  color: var(--text-muted);
  font-size: 0.9em;
  word-break: break-word;
}

@media (max-width: 720px) {
  li {
    grid-template-columns: 1fr auto;
  }

  .detail {
    grid-column: 1 / -1;
  }
}
</style>
