<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import AppShell from '../components/layout/AppShell.vue'
import BaseAlert from '../components/ui/BaseAlert.vue'
import BaseBadge from '../components/ui/BaseBadge.vue'
import BaseButton from '../components/ui/BaseButton.vue'
import BaseSpinner from '../components/ui/BaseSpinner.vue'
import { readHealth } from '../api/health'
import type { HealthReport } from '../api/health'

const { t, te } = useI18n()

const report = ref<HealthReport | null>(null)
const loading = ref(false)
const failed = ref(false)

const services = computed(() =>
  Object.entries(report.value?.services ?? {}).map(([key, service]) => ({
    key,
    name: serviceName(key),
    healthy: service.healthy,
    detail: service.detail ?? ''
  }))
)

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
    <div class="page">
      <header class="head">
        <div>
          <h2>{{ t('status.title') }}</h2>
          <p class="subtitle">{{ t('status.subtitle') }}</p>
        </div>
        <BaseButton :disabled="loading" @click="load">{{ t('status.refresh') }}</BaseButton>
      </header>

      <BaseSpinner v-if="loading && !report" :label="t('common.loading')" />
      <BaseAlert v-else-if="failed" tone="negative">{{ t('common.unexpectedError') }}</BaseAlert>

      <template v-else-if="report">
        <BaseAlert :tone="report.healthy ? 'positive' : 'negative'">
          {{ report.healthy ? t('status.allHealthy') : t('status.someUnhealthy') }}
        </BaseAlert>

        <div class="grid">
          <article v-for="service in services" :key="service.key" class="service">
            <span class="key">{{ service.key }}</span>
            <strong class="name">{{ service.name }}</strong>
            <div class="state">
              <BaseBadge :tone="service.healthy ? 'positive' : 'negative'">
                {{ service.healthy ? t('status.healthy') : t('status.unhealthy') }}
              </BaseBadge>
            </div>
            <p v-if="service.detail" class="detail">{{ service.detail }}</p>
          </article>
        </div>
      </template>
    </div>
  </AppShell>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: var(--rm-space-4);
}

.head {
  display: flex;
  align-items: flex-end;
  gap: var(--rm-space-3);
  flex-wrap: wrap;
}

.head div {
  margin-right: auto;
}

h2 {
  font-size: 26px;
}

.subtitle {
  margin: 3px 0 0;
  color: var(--rm-muted);
  font-size: 13px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 240px), 1fr));
  gap: var(--rm-space-4);
}

.service {
  display: flex;
  flex-direction: column;
  gap: var(--rm-space-3);
  padding: var(--rm-space-4);
  background: var(--rm-panel);
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: var(--rm-radius);
  box-shadow: var(--rm-lift) var(--rm-lift) 0 var(--rm-shadow);
}

.key {
  font-family: var(--rm-font-mono);
  font-size: 10.5px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--rm-muted);
}

.name {
  font-family: var(--rm-font-display);
  font-size: 18px;
}

.state {
  display: flex;
  align-items: center;
  gap: var(--rm-space-2);
}

.detail {
  margin: 0;
  font-family: var(--rm-font-mono);
  font-size: 11px;
  color: var(--rm-muted);
  overflow-wrap: anywhere;
}
</style>
