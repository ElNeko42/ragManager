<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import AppShell from '../components/layout/AppShell.vue'
import BaseAlert from '../components/ui/BaseAlert.vue'
import BaseBadge from '../components/ui/BaseBadge.vue'
import BaseSpinner from '../components/ui/BaseSpinner.vue'
import { listCollections, listFolders } from '../api/drive'
import type { Collection, Folder } from '../api/drive'

const { t } = useI18n()

const collections = ref<Collection[]>([])
const folders = ref<Folder[]>([])
const loading = ref(false)
const failure = ref('')

const cards = computed(() =>
  collections.value.map((collection) => ({
    id: collection.collection_id,
    name: collection.name,
    isDefault: collection.is_default,
    facts: [
      {
        key: t('collections.provider'),
        value:
          collection.provider === 'local' ? t('collections.local') : t('collections.remote')
      },
      { key: t('collections.model'), value: collection.model_name },
      { key: t('collections.dimensions'), value: String(collection.vector_size) },
      { key: t('collections.endpoint'), value: collection.base_url || '—' }
    ],
    usage: folders.value
      .filter((folder) => folder.collection === collection.collection_id)
      .map((folder) => (folder.is_root ? t('drive.everything') : folder.name))
      .join(' · ')
  }))
)

/**
 * Reads the collections together with the folders that point at them.
 */
async function load(): Promise<void> {
  loading.value = true
  failure.value = ''
  try {
    const [cols, tree] = await Promise.all([listCollections(), listFolders()])
    collections.value = cols
    folders.value = tree
  } catch {
    failure.value = t('common.unexpectedError')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <AppShell>
    <div class="page">
      <header>
        <h2>{{ t('collections.title') }}</h2>
        <p class="subtitle">{{ t('collections.subtitle') }}</p>
      </header>

      <BaseAlert v-if="failure" tone="negative">{{ failure }}</BaseAlert>
      <BaseSpinner v-if="loading" :label="t('common.loading')" />

      <div class="grid">
        <article v-for="card in cards" :key="card.id" class="card">
          <div class="head">
            <strong class="name">{{ card.name }}</strong>
            <BaseBadge v-if="card.isDefault" tone="positive">
              {{ t('collections.default') }}
            </BaseBadge>
          </div>

          <dl class="facts">
            <div v-for="fact in card.facts" :key="fact.key">
              <dt>{{ fact.key }}</dt>
              <dd>{{ fact.value }}</dd>
            </div>
          </dl>

          <span class="usage">{{ card.usage || t('collections.unused') }}</span>
        </article>
      </div>
    </div>
  </AppShell>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: var(--rm-space-4);
}

h2 {
  font-size: 26px;
}

.subtitle {
  margin: 3px 0 0;
  color: var(--rm-muted);
  font-size: 13px;
  max-width: 70ch;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));
  gap: var(--rm-space-4);
}

.card {
  display: flex;
  flex-direction: column;
  gap: 11px;
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
  gap: 9px;
  flex-wrap: wrap;
}

.name {
  font-family: var(--rm-font-mono);
  font-size: 15px;
  overflow-wrap: anywhere;
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
  font-family: var(--rm-font-mono);
  font-size: 12px;
  text-align: right;
  overflow-wrap: anywhere;
}

.usage {
  font-family: var(--rm-font-mono);
  font-size: 10.5px;
  color: var(--rm-muted);
  overflow-wrap: anywhere;
}
</style>
