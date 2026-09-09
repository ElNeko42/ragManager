<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import AppShell from '../components/layout/AppShell.vue'
import BaseAlert from '../components/ui/BaseAlert.vue'
import BaseButton from '../components/ui/BaseButton.vue'
import BaseSegmented from '../components/ui/BaseSegmented.vue'
import BaseSpinner from '../components/ui/BaseSpinner.vue'
import DocumentCard from '../components/drive/DocumentCard.vue'
import DocumentDetail from '../components/drive/DocumentDetail.vue'
import DocumentRow from '../components/drive/DocumentRow.vue'
import FolderCard from '../components/drive/FolderCard.vue'
import FolderTree from '../components/drive/FolderTree.vue'
import UploadZone from '../components/drive/UploadZone.vue'
import { useDriveStore } from '../stores/drive'

const { t } = useI18n()
const drive = useDriveStore()

const view = ref('grid')
const busy = ref(false)
const failure = ref('')

const views = computed(() => [
  { value: 'grid', label: t('drive.grid') },
  { value: 'list', label: t('drive.list') }
])

const folderName = computed(() =>
  drive.current?.is_root ? t('drive.everything') : (drive.current?.name ?? '')
)

const breadcrumb = computed(() =>
  drive.path.map((folder) => (folder.is_root ? '' : folder.name)).join('/') || '/'
)

const meta = computed(() =>
  [breadcrumb.value, t('drive.documentCount', drive.documents.length)].join('  ·  ')
)

const selectedPath = computed(() =>
  drive.selected ? `${breadcrumb.value}/${drive.selected.name}`.replace('//', '/') : ''
)

const subfolders = computed(() =>
  drive.children.map((folder) => ({
    id: folder.folder_id,
    name: folder.name,
    hasChildren: drive.folders.some((f) => f.parent === folder.folder_id),
    meta: t('drive.folderCount', drive.folders.filter((f) => f.parent === folder.folder_id).length)
  }))
)

/**
 * Runs one panel action, showing why it failed instead of failing silently.
 */
async function run(action: () => Promise<unknown>): Promise<void> {
  busy.value = true
  failure.value = ''
  try {
    await action()
  } catch {
    failure.value = t('common.unexpectedError')
  } finally {
    busy.value = false
  }
}

/**
 * Creates a folder under a name that is free among its siblings.
 */
function addFolder(): void {
  const base = t('drive.newFolderName')
  const taken = new Set(drive.children.map((f) => f.name))
  let name = base
  let n = 2
  while (taken.has(name)) {
    name = `${base} ${n}`
    n += 1
  }
  void run(() => drive.addFolder(name))
}

onMounted(() => void run(() => drive.start()))
onUnmounted(() => drive.stop())
</script>

<template>
  <AppShell>
    <div class="drive">
      <aside class="sidebar">
        <header class="sidehead">
          <span class="eyebrow">{{ t('drive.tree') }}</span>
          <button type="button" class="add" :title="t('drive.newFolder')" @click="addFolder">
            +
          </button>
        </header>

        <FolderTree
          :folders="drive.folders"
          :selected="drive.folderId"
          @open="(id) => run(() => drive.open(id))"
        />

        <div class="rule" />

        <div class="collection">
          <span class="eyebrow">{{ t('drive.collection') }}</span>
          <span class="chip">{{ drive.collectionName }}</span>
        </div>
      </aside>

      <section class="content">
        <header class="head">
          <div class="titling">
            <h2>{{ folderName }}</h2>
            <p class="meta">{{ meta }}</p>
          </div>
          <BaseSegmented v-model="view" :segments="views" :label="t('drive.viewLabel')" />
        </header>

        <UploadZone @files="(files) => run(() => drive.upload(files))" />

        <BaseAlert v-if="failure" tone="negative">{{ failure }}</BaseAlert>
        <BaseSpinner v-if="drive.loading || busy" :label="t('common.loading')" />

        <template v-if="subfolders.length">
          <div class="section">
            <span class="eyebrow">{{ t('drive.subfolders') }}</span>
            <BaseButton @click="addFolder">{{ t('drive.newFolder') }}</BaseButton>
          </div>
          <div class="cards">
            <FolderCard
              v-for="folder in subfolders"
              :key="folder.id"
              :name="folder.name"
              :meta="folder.meta"
              :has-children="folder.hasChildren"
              @open="run(() => drive.open(folder.id))"
            />
          </div>
          <span class="eyebrow">{{ t('drive.filesHere') }}</span>
        </template>

        <p v-if="!drive.documents.length && !drive.loading" class="empty">
          {{ t('drive.emptyFolder') }}
        </p>

        <div v-else-if="view === 'grid'" class="cards">
          <DocumentCard
            v-for="document in drive.documents"
            :key="document.document_id"
            :document="document"
            :selected="drive.selected?.document_id === document.document_id"
            @select="run(() => drive.select(document.document_id))"
            @active="(value) => run(() => drive.setActive(document.document_id, value))"
          />
        </div>

        <div v-else class="table">
          <div class="thead">
            <span>{{ t('drive.colName') }}</span>
            <span>{{ t('drive.colSwitch') }}</span>
            <span>{{ t('drive.colStatus') }}</span>
          </div>
          <DocumentRow
            v-for="document in drive.documents"
            :key="document.document_id"
            :document="document"
            :selected="drive.selected?.document_id === document.document_id"
            @select="run(() => drive.select(document.document_id))"
            @active="(value) => run(() => drive.setActive(document.document_id, value))"
          />
        </div>
      </section>

      <DocumentDetail
        v-if="drive.selected"
        :document="drive.selected"
        :path="selectedPath"
        :collection="drive.collectionName"
        @active="(value) => run(() => drive.setActive(drive.selected!.document_id, value))"
        @rename="(name) => run(() => drive.rename(drive.selected!.document_id, name))"
        @remove="run(() => drive.remove(drive.selected!.document_id))"
      />
      <aside v-else class="placeholder">
        <span class="eyebrow">{{ t('drive.detail') }}</span>
        <p>{{ t('drive.pickDocument') }}</p>
      </aside>
    </div>
  </AppShell>
</template>

<style scoped>
.drive {
  display: grid;
  grid-template-columns: minmax(0, 210px) minmax(320px, 1fr) minmax(0, 320px);
  gap: 18px;
  align-items: start;
}

.sidebar,
.placeholder {
  display: flex;
  flex-direction: column;
  gap: var(--rm-space-3);
  padding: var(--rm-space-4);
  background: var(--rm-panel);
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: var(--rm-radius);
  box-shadow: var(--rm-lift) var(--rm-lift) 0 var(--rm-shadow);
}

.sidehead,
.section {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--rm-space-2);
}

.eyebrow {
  font-family: var(--rm-font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--rm-muted);
}

.add {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 7px;
  background: var(--rm-lime);
  color: #17131f;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}

.add:hover {
  background: var(--rm-pink);
}

.rule {
  height: var(--rm-border-width);
  background: var(--rm-line);
}

.collection {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.chip {
  padding: 5px 9px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 8px;
  background: var(--rm-panel2);
  font-family: var(--rm-font-mono);
  font-size: 12px;
  overflow-wrap: anywhere;
}

.content {
  display: flex;
  flex-direction: column;
  gap: var(--rm-space-3);
  min-width: 0;
}

.head {
  display: flex;
  align-items: center;
  gap: var(--rm-space-3);
  flex-wrap: wrap;
  padding: var(--rm-space-3) var(--rm-space-4);
  background: var(--rm-panel);
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: var(--rm-radius);
  box-shadow: var(--rm-lift) var(--rm-lift) 0 var(--rm-shadow);
}

.titling {
  margin-right: auto;
  min-width: 0;
}

h2 {
  font-size: 22px;
}

.meta {
  margin: 2px 0 0;
  font-family: var(--rm-font-mono);
  font-size: 11px;
  color: var(--rm-muted);
  overflow-wrap: anywhere;
}

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: var(--rm-space-4);
}

.table {
  background: var(--rm-panel);
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: var(--rm-radius);
  box-shadow: var(--rm-lift) var(--rm-lift) 0 var(--rm-shadow);
  overflow: hidden;
}

.thead {
  display: grid;
  grid-template-columns: minmax(80px, 1fr) auto auto;
  gap: var(--rm-space-3);
  padding: 9px var(--rm-space-4);
  background: var(--rm-ink);
  color: var(--rm-panel);
  font-family: var(--rm-font-mono);
  font-size: 10.5px;
  letter-spacing: 0.1em;
}

.empty {
  margin: 0;
  padding: var(--rm-space-4);
  border: var(--rm-border-width) dashed var(--rm-border);
  border-radius: 14px;
  color: var(--rm-muted);
}

@media (max-width: 1100px) {
  .drive {
    grid-template-columns: 1fr;
  }
}
</style>
