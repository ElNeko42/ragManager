<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import AppShell from '../components/layout/AppShell.vue'
import BaseAlert from '../components/ui/BaseAlert.vue'
import BaseBadge from '../components/ui/BaseBadge.vue'
import BaseButton from '../components/ui/BaseButton.vue'
import BaseField from '../components/ui/BaseField.vue'
import BaseInput from '../components/ui/BaseInput.vue'
import BaseModal from '../components/ui/BaseModal.vue'
import BaseSegmented from '../components/ui/BaseSegmented.vue'
import BaseSelect from '../components/ui/BaseSelect.vue'
import BaseSpinner from '../components/ui/BaseSpinner.vue'
import ConfirmDialog from '../components/ui/ConfirmDialog.vue'
import UnsavedGuard from '../components/ui/UnsavedGuard.vue'
import { useAction } from '../composables/useAction'
import {
  createCollection,
  deleteCollection,
  listCollections,
  listFolders,
  setDefaultCollection,
  updateFolder
} from '../api/drive'
import type { Collection, Folder } from '../api/drive'

const { t } = useI18n()
const { busy, failure, run, clear } = useAction()

const collections = ref<Collection[]>([])
const folders = ref<Folder[]>([])
const loading = ref(false)

const creating = ref(false)
const removing = ref<Collection | null>(null)
const switchingBase = ref('')

const draft = ref({
  name: '',
  provider: 'local',
  base_url: '',
  model_name: '',
  vector_size: '384',
  is_default: false
})

const providers = computed(() => [
  { value: 'local', label: t('collections.local') },
  { value: 'api', label: t('collections.remote') }
])

const root = computed(() => folders.value.find((folder) => folder.is_root) ?? null)

const baseModel = computed(
  () =>
    collections.value.find((c) => c.collection_id === root.value?.collection)?.name ?? ''
)

const options = computed(() =>
  collections.value.map((collection) => ({
    value: collection.collection_id,
    label: collection.name
  }))
)

const draftTouched = computed(() =>
  Boolean(
    draft.value.name ||
      draft.value.model_name ||
      draft.value.base_url ||
      draft.value.provider !== 'local' ||
      draft.value.vector_size !== '384' ||
      draft.value.is_default
  )
)

const baseTouched = computed(
  () => Boolean(root.value) && switchingBase.value !== root.value?.collection
)

const dirty = computed(() => (creating.value && draftTouched.value) || baseTouched.value)

const environmentKey = computed(
  () => `EMBEDDING_API_KEY_${draft.value.name.toUpperCase().replace(/-/g, '_')}`
)

/**
 * Counts the folders pointing at one collection.
 *
 * A collection nothing points at can be removed; one in use cannot, and the
 * card says so before the owner tries.
 */
function usersOf(collection: Collection): Folder[] {
  return folders.value.filter((folder) => folder.collection === collection.collection_id)
}

const cards = computed(() =>
  collections.value.map((collection) => ({
    collection,
    id: collection.collection_id,
    name: collection.name,
    isDefault: collection.is_default,
    isBase: collection.collection_id === root.value?.collection,
    inUse: usersOf(collection).length > 0,
    facts: [
      {
        key: t('collections.provider'),
        value:
          collection.provider === 'local' ? t('collections.local') : t('collections.remote')
      },
      { key: t('collections.model'), value: collection.model_name },
      { key: t('collections.dimensions'), value: String(collection.vector_size) },
      { key: t('collections.endpoint'), value: collection.base_url || '\u2014' }
    ],
    usage: usersOf(collection)
      .map((folder) => (folder.is_root ? t('drive.everything') : folder.name))
      .join(' \u00b7 ')
  }))
)

/**
 * Reads the collections together with the folders that point at them.
 */
async function load(): Promise<void> {
  loading.value = true
  try {
    const [cols, tree] = await Promise.all([listCollections(), listFolders()])
    collections.value = cols
    folders.value = tree
    switchingBase.value = root.value?.collection ?? ''
  } finally {
    loading.value = false
  }
}

/**
 * Opens the registration form on a clean draft.
 */
function startCreate(): void {
  draft.value = {
    name: '',
    provider: 'local',
    base_url: '',
    model_name: '',
    vector_size: '384',
    is_default: false
  }
  clear()
  creating.value = true
}

/**
 * Registers the model the form describes.
 *
 * The width is sent as a number because it is what the vectors will be, and a
 * collection registered with the wrong one fails on its first document rather
 * than at the moment the mistake is made.
 */
function submit(): void {
  const size = Number(draft.value.vector_size)
  if (!Number.isInteger(size) || size < 1) {
    return
  }
  void run(async () => {
    await createCollection({
      name: draft.value.name.trim(),
      provider: draft.value.provider === 'api' ? 'api' : 'local',
      base_url: draft.value.provider === 'api' ? draft.value.base_url.trim() : '',
      model_name: draft.value.model_name.trim(),
      vector_size: size,
      is_default: draft.value.is_default
    })
    creating.value = false
    await load()
  })
}

/**
 * Leaves the registration form, dropping whatever it was complaining about.
 */
function cancelCreate(): void {
  creating.value = false
  clear()
}

/**
 * Makes one collection the one new folders inherit by default.
 */
function makeDefault(collection: Collection): void {
  void run(async () => {
    await setDefaultCollection(collection.collection_id, true)
    await load()
  })
}

/**
 * Removes the collection the owner has agreed to lose.
 */
function confirmRemove(): void {
  const collection = removing.value
  removing.value = null
  if (!collection) {
    return
  }
  void run(async () => {
    await deleteCollection(collection.collection_id)
    await load()
  })
}

/**
 * Points the root folder at another model.
 *
 * Whatever sits directly in the root was vectorised with the model it is
 * leaving, so it goes back to the queue. Folders below the root keep the model
 * they were created with.
 */
function changeBase(): void {
  const wanted = switchingBase.value
  const current = root.value
  if (!current || !wanted || wanted === current.collection) {
    return
  }
  void run(async () => {
    await updateFolder(current.folder_id, { collection: wanted })
    await load()
  })
}

onMounted(() => void run(load))
</script>

<template>
  <AppShell>
    <UnsavedGuard :dirty="dirty" />
    <div class="page">
      <header class="head">
        <div>
          <h2>{{ t('collections.title') }}</h2>
          <p class="subtitle">{{ t('collections.subtitle') }}</p>
        </div>
        <BaseButton variant="primary" @click="startCreate">
          {{ t('collections.newCollection') }}
        </BaseButton>
      </header>

      <BaseAlert v-if="failure && !creating" tone="negative">{{ failure }}</BaseAlert>
      <BaseSpinner v-if="loading || busy" :label="t('common.loading')" />

      <section class="base">
        <div class="basetext">
          <span class="eyebrow">{{ t('collections.baseModel') }}</span>
          <p class="hint">{{ t('collections.baseHint') }}</p>
        </div>
        <div class="basepick">
          <BaseSelect
            id="base-model"
            v-model="switchingBase"
            :options="options"
            :disabled="busy || !options.length"
          />
          <BaseButton
            variant="primary"
            :disabled="busy || switchingBase === root?.collection"
            @click="changeBase"
          >
            {{ t('collections.applyBase') }}
          </BaseButton>
        </div>
      </section>

      <p v-if="!cards.length && !loading" class="empty">{{ t('collections.none') }}</p>

      <div v-else class="grid">
        <article v-for="card in cards" :key="card.id" class="card">
          <div class="cardhead">
            <strong class="name">{{ card.name }}</strong>
            <span class="tags">
              <BaseBadge v-if="card.isBase" tone="neutral">
                {{ t('collections.base') }}
              </BaseBadge>
              <BaseBadge v-if="card.isDefault" tone="positive">
                {{ t('collections.default') }}
              </BaseBadge>
            </span>
          </div>

          <dl class="facts">
            <div v-for="fact in card.facts" :key="fact.key">
              <dt>{{ fact.key }}</dt>
              <dd>{{ fact.value }}</dd>
            </div>
          </dl>

          <span class="usage">{{ card.usage || t('collections.unused') }}</span>

          <div class="tools">
            <BaseButton
              v-if="!card.isDefault"
              variant="quiet"
              :disabled="busy"
              @click="makeDefault(card.collection)"
            >
              {{ t('collections.makeDefault') }}
            </BaseButton>
            <BaseButton
              variant="quiet"
              :disabled="busy || card.inUse"
              :title="card.inUse ? t('collections.inUse') : ''"
              @click="removing = card.collection"
            >
              {{ t('collections.delete') }}
            </BaseButton>
          </div>
        </article>
      </div>
    </div>

    <BaseModal
      v-if="creating"
      :title="t('collections.newCollection')"
      @close="cancelCreate"
    >
      <form class="form" @submit.prevent="submit">
        <BaseAlert v-if="failure" tone="negative">{{ failure }}</BaseAlert>

        <BaseField
          :label="t('collections.name')"
          for-id="collection-name"
          :hint="t('collections.nameHint')"
        >
          <BaseInput id="collection-name" v-model="draft.name" required :disabled="busy" />
        </BaseField>

        <BaseField :label="t('collections.provider')" for-id="collection-provider">
          <BaseSegmented
            v-model="draft.provider"
            :segments="providers"
            :label="t('collections.provider')"
          />
        </BaseField>

        <BaseField
          v-if="draft.provider === 'api'"
          :label="t('collections.endpoint')"
          for-id="collection-url"
          :hint="t('collections.endpointHint')"
        >
          <BaseInput id="collection-url" v-model="draft.base_url" required :disabled="busy" />
        </BaseField>

        <BaseField
          :label="t('collections.model')"
          for-id="collection-model"
          :hint="draft.provider === 'api' ? t('collections.modelHintApi') : t('collections.modelHintLocal')"
        >
          <BaseInput id="collection-model" v-model="draft.model_name" required :disabled="busy" />
        </BaseField>

        <BaseField
          :label="t('collections.dimensions')"
          for-id="collection-size"
          :hint="t('collections.dimensionsHint')"
        >
          <BaseInput
            id="collection-size"
            v-model="draft.vector_size"
            type="number"
            required
            :disabled="busy"
          />
        </BaseField>

        <BaseAlert v-if="draft.provider === 'api' && draft.name.trim()" tone="info">
          {{ t('collections.keyNotice', { key: environmentKey }) }}
        </BaseAlert>

        <div class="buttons">
          <BaseButton variant="quiet" :disabled="busy" @click="cancelCreate">
            {{ t('drive.cancel') }}
          </BaseButton>
          <BaseButton type="submit" variant="primary" :disabled="busy">
            {{ t('collections.createGo') }}
          </BaseButton>
        </div>
      </form>
    </BaseModal>

    <ConfirmDialog
      v-if="removing"
      :title="t('collections.delete')"
      :question="t('collections.deleteAsk', { name: removing.name })"
      :consequences="[t('collections.deleteCost.registration'), t('collections.deleteCost.vectors')]"
      :confirm-label="t('collections.deleteYes')"
      :busy="busy"
      @confirm="confirmRemove"
      @cancel="removing = null"
    />
  </AppShell>
</template>

<style scoped>
.buttons {
  display: flex;
  justify-content: flex-end;
  gap: var(--rm-space-2);
  padding-top: var(--rm-space-2);
  border-top: var(--rm-border-width) dotted var(--rm-line);
}

.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--rm-space-3);
  flex-wrap: wrap;
}

.base {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--rm-space-4);
  flex-wrap: wrap;
  padding: var(--rm-space-4);
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 14px;
  background: var(--rm-panel);
  box-shadow: 4px 4px 0 var(--rm-shadow);
}

.basetext {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.basepick {
  display: flex;
  align-items: center;
  gap: var(--rm-space-2);
  min-width: 260px;
}

.hint {
  margin: 0;
  font-size: 12.5px;
  color: var(--rm-muted);
}

.cardhead {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--rm-space-2);
}

.tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.tools {
  display: flex;
  gap: var(--rm-space-2);
  padding-top: var(--rm-space-2);
  border-top: var(--rm-border-width) dotted var(--rm-line);
}

.form {
  display: flex;
  flex-direction: column;
  gap: var(--rm-space-4);
}

.empty {
  padding: var(--rm-space-5);
  border: var(--rm-border-width) dashed var(--rm-line);
  border-radius: 14px;
  color: var(--rm-muted);
  text-align: center;
}

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
