<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import AppShell from '../components/layout/AppShell.vue'
import BaseAlert from '../components/ui/BaseAlert.vue'
import BaseButton from '../components/ui/BaseButton.vue'
import BaseIcon from '../components/ui/BaseIcon.vue'
import BaseField from '../components/ui/BaseField.vue'
import BaseInput from '../components/ui/BaseInput.vue'
import BaseModal from '../components/ui/BaseModal.vue'
import BaseSegmented from '../components/ui/BaseSegmented.vue'
import BaseSelect from '../components/ui/BaseSelect.vue'
import BaseSpinner from '../components/ui/BaseSpinner.vue'
import ConfirmDialog from '../components/ui/ConfirmDialog.vue'
import UnsavedGuard from '../components/ui/UnsavedGuard.vue'
import DocumentCard from '../components/drive/DocumentCard.vue'
import DocumentDetail from '../components/drive/DocumentDetail.vue'
import DocumentRow from '../components/drive/DocumentRow.vue'
import FolderCard from '../components/drive/FolderCard.vue'
import FolderTree from '../components/drive/FolderTree.vue'
import UploadZone from '../components/drive/UploadZone.vue'
import { useAction } from '../composables/useAction'
import { useMediaQuery } from '../composables/useMediaQuery'
import { useDriveStore } from '../stores/drive'
import type { Folder } from '../api/drive'

const { t } = useI18n()
const router = useRouter()
const drive = useDriveStore()

const view = ref('grid')
const narrow = useMediaQuery('(max-width: 900px)')
const treeOpen = ref(false)
const dragging = ref(false)
let hovering = 0
const renamingFolder = ref<Folder | null>(null)
const folderDraft = ref('')
const deletingFolder = ref<Folder | null>(null)
const pendingMove = ref<string | null>(null)
const addingFolder = ref(false)
const newFolder = ref({ name: '', collection: '' })
const { busy, failure, run, clear } = useAction()

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
  drive.selected ? `${breadcrumb.value}/${drive.selected.name}`.replaceAll('//', '/') : ''
)

const subfolders = computed(() =>
  drive.children.map((folder) => ({
    folder,
    id: folder.folder_id,
    name: folder.name,
    hasChildren: drive.folders.some((f) => f.parent === folder.folder_id),
    meta: t('drive.folderCount', drive.folders.filter((f) => f.parent === folder.folder_id).length)
  }))
)

watch(
  () => drive.folderId,
  () => {
    pendingMove.value = null
  }
)

/**
 * Counts the folders that would go down with one folder.
 */
function descendantCount(id: string): number {
  const gone = new Set([id])
  let grew = true
  while (grew) {
    grew = false
    for (const folder of drive.folders) {
      if (folder.parent && gone.has(folder.parent) && !gone.has(folder.folder_id)) {
        gone.add(folder.folder_id)
        grew = true
      }
    }
  }
  return gone.size - 1
}

const folderDeletionCost = computed(() => [
  t('drive.deleteFolderCost.subfolders', {
    count: deletingFolder.value ? descendantCount(deletingFolder.value.folder_id) : 0
  }),
  t('drive.deleteFolderCost.documents'),
  t('drive.deleteFolderCost.vectors')
])

/**
 * Builds the full path of a folder, so two folders alike are told apart.
 */
function pathOf(id: string): string {
  const names: string[] = []
  let node = drive.folders.find((f) => f.folder_id === id) ?? null
  while (node) {
    names.unshift(node.is_root ? t('drive.everything') : node.name)
    const parent: string | null = node.parent
    node = drive.folders.find((f) => f.folder_id === parent) ?? null
  }
  return names.join(' / ')
}

const destinations = computed(() =>
  drive.folders
    .filter((folder) => folder.folder_id !== drive.folderId)
    .map((folder) => ({ id: folder.folder_id, label: pathOf(folder.folder_id) }))
    .sort((a, b) => a.label.localeCompare(b.label))
)

/**
 * Reports whether a move would land the document under another embedding model.
 *
 * Vectors of one model mean nothing to another, so such a move throws away
 * what was indexed and queues the work again. The owner is told before it
 * happens rather than discovering the document unsearchable afterwards.
 */
function crossesCollection(folderId: string): boolean {
  const from = drive.folders.find((f) => f.folder_id === drive.folderId)
  const to = drive.folders.find((f) => f.folder_id === folderId)
  return Boolean(from && to && from.collection !== to.collection)
}

/**
 * Moves the open document, asking first when the move costs its index.
 */
function askMove(folderId: string): void {
  if (crossesCollection(folderId)) {
    pendingMove.value = folderId
    return
  }
  moveTo(folderId)
}

/**
 * Carries out a move that has been decided on.
 */
function moveTo(folderId: string): void {
  const documentId = drive.selected?.document_id
  pendingMove.value = null
  if (documentId) {
    void run(() => drive.move(documentId, folderId))
  }
}

/**
 * Deletes a folder once the owner has agreed to lose what it holds.
 */
function confirmDeleteFolder(): void {
  const folder = deletingFolder.value
  deletingFolder.value = null
  if (folder) {
    void run(() => drive.removeFolder(folder.folder_id))
  }
}

/**
 * Opens the rename box on one folder, wherever it was asked for.
 */
function startRenameFolder(folder: Folder): void {
  folderDraft.value = folder.name
  renamingFolder.value = folder
}

/**
 * Applies the new folder name, unless it was left empty or unchanged.
 */
function commitRenameFolder(): void {
  const folder = renamingFolder.value
  const name = folderDraft.value.trim()
  renamingFolder.value = null
  if (!folder || !name || name === folder.name) {
    return
  }
  void run(() => drive.renameFolder(folder.folder_id, name))
}

/**
 * Opens the permissions panel already showing one folder.
 *
 * Deciding what an agent may read starts from a folder far more often than
 * from an agent, so the folder travels in the link instead of being hunted
 * for again in the other screen.
 */
function openPermissions(folder: Folder): void {
  void router.push({ name: 'permissions', query: { folder: folder.folder_id } })
}

const atRoot = computed(() => drive.current?.is_root === true)

const dirty = computed(() => {
  if (addingFolder.value) {
    return newFolder.value.name.trim() !== ''
  }
  if (renamingFolder.value) {
    return folderDraft.value.trim() !== renamingFolder.value.name
  }
  return false
})

const collectionOptions = computed(() =>
  drive.collections.map((collection) => ({
    value: collection.collection_id,
    label: collection.name
  }))
)

const inheritedCollection = computed(
  () =>
    drive.collections.find((c) => c.collection_id === drive.current?.collection)?.name ?? ''
)

/**
 * Leaves the new folder form, dropping whatever it was complaining about.
 */
function cancelAddFolder(): void {
  addingFolder.value = false
  clear()
}

/**
 * Leaves the rename box, dropping whatever it was complaining about.
 */
function cancelRenameFolder(): void {
  renamingFolder.value = null
  clear()
}

/**
 * Opens the form for a new folder inside the one on screen.
 *
 * The model is offered only at the first level. Deeper down a folder inherits
 * its parent's, so that one branch is searched with one model throughout, and
 * the form says which one it will be rather than staying silent about it.
 */
function startAddFolder(): void {
  newFolder.value = {
    name: '',
    collection: atRoot.value ? (drive.current?.collection ?? '') : ''
  }
  clear()
  addingFolder.value = true
}

/**
 * Creates the folder the form describes.
 */
function submitFolder(): void {
  const name = newFolder.value.name.trim()
  if (!name) {
    return
  }
  const collection = atRoot.value ? newFolder.value.collection : undefined
  void run(async () => {
    await drive.addFolder(name, collection || undefined)
    addingFolder.value = false
  })
}

/**
 * Reports whether what is being dragged is files rather than page furniture.
 *
 * Dragging the selection of a name, or a link, or a folder row also fires
 * these events, and none of them are something to upload.
 */
function carriesFiles(event: DragEvent): boolean {
  return Array.from(event.dataTransfer?.types ?? []).includes('Files')
}

/**
 * Counts the drag into the page, so the invitation appears once.
 *
 * A drag crossing the page raises an enter for every element it passes over
 * and a leave for every element it passes off, so the two are counted against
 * each other rather than treated as arrival and departure.
 */
function onDragEnter(event: DragEvent): void {
  if (!carriesFiles(event)) {
    return
  }
  hovering += 1
  dragging.value = true
}

/**
 * Tells the browser this page will take the files.
 *
 * Without this the drop never happens: a page that does not answer the drag
 * is a page the browser hands the file to itself, replacing the panel with
 * whatever was dropped.
 */
function onDragOver(event: DragEvent): void {
  if (!carriesFiles(event)) {
    return
  }
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'copy'
  }
}

/**
 * Counts the drag back out again, and gives up the invitation at zero.
 */
function onDragLeave(event: DragEvent): void {
  if (!carriesFiles(event)) {
    return
  }
  hovering = Math.max(0, hovering - 1)
  if (hovering === 0) {
    dragging.value = false
  }
}

/**
 * Clears the invitation when a drag ends without ever being dropped.
 */
function onDragEnd(): void {
  hovering = 0
  dragging.value = false
}

/**
 * Takes files dropped anywhere on the page into the folder that is open.
 */
function onDrop(event: DragEvent): void {
  if (!carriesFiles(event)) {
    return
  }
  event.preventDefault()
  hovering = 0
  dragging.value = false
  const files = Array.from(event.dataTransfer?.files ?? [])
  if (files.length) {
    void run(() => drive.upload(files))
  }
}

onMounted(() => {
  void run(() => drive.start())
  window.addEventListener('dragenter', onDragEnter)
  window.addEventListener('dragover', onDragOver)
  window.addEventListener('dragleave', onDragLeave)
  window.addEventListener('drop', onDrop)
  window.addEventListener('dragend', onDragEnd)
})

onUnmounted(() => {
  drive.stop()
  window.removeEventListener('dragenter', onDragEnter)
  window.removeEventListener('dragover', onDragOver)
  window.removeEventListener('dragleave', onDragLeave)
  window.removeEventListener('drop', onDrop)
  window.removeEventListener('dragend', onDragEnd)
})
</script>

<template>
  <AppShell>
    <UnsavedGuard :dirty="dirty" />

    <div v-if="dragging" class="catcher" aria-hidden="true">
      <div class="invitation">
        <BaseIcon name="upload" :size="32" />
        <strong>{{ t('drive.dropAnywhere') }}</strong>
        <span class="target">{{ t('drive.dropInto', { name: folderName }) }}</span>
      </div>
    </div>

    <div class="drive">
      <aside class="sidebar">
        <header class="sidehead">
          <button
            v-if="narrow"
            type="button"
            class="fold"
            :aria-expanded="treeOpen"
            aria-controls="folder-tree"
            @click="treeOpen = !treeOpen"
          >
            <BaseIcon :name="treeOpen ? 'chevronDown' : 'chevronRight'" :size="16" />
            <span class="eyebrow">{{ t('drive.tree') }}</span>
          </button>
          <span v-else class="eyebrow">{{ t('drive.tree') }}</span>
          <button type="button" class="add" :title="t('drive.newFolder')" @click="startAddFolder">
            <BaseIcon name="plus" :size="18" />
          </button>
        </header>

        <div id="folder-tree" :class="['folding', { folded: narrow && !treeOpen }]">
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
        </div>
      </aside>

      <section class="content">
        <header class="head">
          <div class="titling">
            <div class="named">
              <h2>{{ folderName }}</h2>
              <template v-if="drive.current">
                <BaseButton
                  v-if="!drive.current.is_root"
                  variant="quiet"
                  @click="startRenameFolder(drive.current)"
                >
                  <BaseIcon name="pencil" :size="15" />
                  {{ t('drive.renameFolder') }}
                </BaseButton>
                <BaseButton variant="quiet" @click="openPermissions(drive.current)">
                  <BaseIcon name="shield" :size="15" />
                  {{ t('drive.folderPermissions') }}
                </BaseButton>
                <BaseButton
                  v-if="!drive.current.is_root"
                  variant="quiet"
                  @click="deletingFolder = drive.current"
                >
                  <BaseIcon name="trash" :size="15" />
                  {{ t('drive.deleteFolder') }}
                </BaseButton>
              </template>
            </div>
            <p class="meta">{{ meta }}</p>
          </div>
          <BaseSegmented v-model="view" :segments="views" :label="t('drive.viewLabel')" />
        </header>

        <UploadZone @files="(files) => run(() => drive.upload(files))" />

        <BaseAlert v-if="failure && !addingFolder && !renamingFolder" tone="negative">
          {{ failure }}
        </BaseAlert>
        <BaseSpinner v-if="drive.loading || busy" :label="t('common.loading')" />

        <template v-if="subfolders.length">
          <div class="section">
            <span class="eyebrow">{{ t('drive.subfolders') }}</span>
            <BaseButton @click="startAddFolder">
              <BaseIcon name="plus" :size="16" />
              {{ t('drive.newFolder') }}
            </BaseButton>
          </div>
          <div class="cards">
            <FolderCard
              v-for="folder in subfolders"
              :key="folder.id"
              :name="folder.name"
              :meta="folder.meta"
              :has-children="folder.hasChildren"
              @open="run(() => drive.open(folder.id))"
              @rename="startRenameFolder(folder.folder)"
              @permissions="openPermissions(folder.folder)"
              @remove="deletingFolder = folder.folder"
            />
          </div>
          <span class="eyebrow">{{ t('drive.filesHere') }}</span>
        </template>

        <p v-if="!drive.documents.length && !drive.loading" class="empty">
          {{ t('drive.emptyFolder') }}
        </p>

        <div v-else-if="drive.documents.length && view === 'grid'" class="cards">
          <DocumentCard
            v-for="document in drive.documents"
            :key="document.document_id"
            :document="document"
            :selected="drive.selected?.document_id === document.document_id"
            @select="run(() => drive.select(document.document_id))"
            @active="(value) => run(() => drive.setActive(document.document_id, value))"
          />
        </div>

        <div v-else-if="drive.documents.length" class="table">
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
        class="pane-detail"
        :document="drive.selected"
        :path="selectedPath"
        :collection="drive.collectionName"
        :destinations="destinations"
        @active="(value) => run(() => drive.setActive(drive.selected!.document_id, value))"
        @rename="(name) => run(() => drive.rename(drive.selected!.document_id, name))"
        @move="askMove"
        @remove="run(() => drive.remove(drive.selected!.document_id))"
      />
      <aside v-else class="placeholder pane-detail">
        <span class="eyebrow">{{ t('drive.detail') }}</span>
        <p>{{ t('drive.pickDocument') }}</p>
      </aside>
    </div>

    <BaseModal v-if="addingFolder" :title="t('drive.newFolder')" @close="cancelAddFolder">
      <form class="folderform" @submit.prevent="submitFolder">
        <BaseAlert v-if="failure" tone="negative">{{ failure }}</BaseAlert>

        <BaseField :label="t('drive.folderName')" for-id="new-folder-name">
          <BaseInput id="new-folder-name" v-model="newFolder.name" required :disabled="busy" />
        </BaseField>

        <BaseField
          v-if="atRoot"
          :label="t('drive.collection')"
          for-id="new-folder-collection"
          :hint="t('drive.collectionHint')"
        >
          <BaseSelect
            id="new-folder-collection"
            v-model="newFolder.collection"
            :options="collectionOptions"
            :disabled="busy"
          />
        </BaseField>
        <BaseAlert v-else tone="info">
          {{ t('drive.inheritsCollection', { name: inheritedCollection }) }}
        </BaseAlert>

        <div class="buttons">
          <BaseButton variant="quiet" :disabled="busy" @click="cancelAddFolder">
            {{ t('drive.cancel') }}
          </BaseButton>
          <BaseButton type="submit" variant="primary" :disabled="busy">
            {{ t('drive.createFolderGo') }}
          </BaseButton>
        </div>
      </form>
    </BaseModal>

    <BaseModal
      v-if="renamingFolder"
      :title="t('drive.renameFolder')"
      @close="cancelRenameFolder"
    >
      <form class="renaming" @submit.prevent="commitRenameFolder">
        <BaseField :label="t('drive.folderName')" for-id="folder-name">
          <BaseInput id="folder-name" v-model="folderDraft" :required="true" :disabled="busy" />
        </BaseField>
        <div class="buttons">
          <BaseButton variant="quiet" :disabled="busy" @click="cancelRenameFolder">
            {{ t('drive.cancel') }}
          </BaseButton>
          <BaseButton type="submit" variant="primary" :disabled="busy">
            {{ t('drive.save') }}
          </BaseButton>
        </div>
      </form>
    </BaseModal>

    <ConfirmDialog
      v-if="deletingFolder"
      :title="t('drive.deleteFolder')"
      :question="t('drive.deleteFolderAsk', { name: deletingFolder.name })"
      :consequences="folderDeletionCost"
      :confirm-label="t('drive.deleteFolderYes')"
      :busy="busy"
      @confirm="confirmDeleteFolder"
      @cancel="deletingFolder = null"
    />

    <ConfirmDialog
      v-if="pendingMove"
      :title="t('drive.moveTitle')"
      :question="t('drive.moveAsk')"
      :consequences="[t('drive.moveCost.discard'), t('drive.moveCost.requeue')]"
      :confirm-label="t('drive.moveYes')"
      :busy="busy"
      @confirm="moveTo(pendingMove)"
      @cancel="pendingMove = null"
    />
  </AppShell>
</template>

<style scoped>
/*
 * The whole page is the drop target, so the whole page says so. It never takes
 * the pointer: the drop is read from the window, and a sheet that swallowed
 * events would take it from the elements underneath.
 */
.catcher {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  padding: var(--rm-space-5);
  background: var(--rm-bg);
  background: color-mix(in srgb, var(--rm-bg) 78%, transparent);
  pointer-events: none;
}

.invitation {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--rm-space-2);
  padding: var(--rm-space-6) var(--rm-space-6);
  border: 3px dashed var(--rm-border);
  border-radius: var(--rm-radius);
  background: var(--rm-panel);
  box-shadow: var(--rm-lift) var(--rm-lift) 0 var(--rm-shadow);
  text-align: center;
}

.invitation strong {
  font-family: var(--rm-font-display);
  font-size: 20px;
}

.target {
  font-family: var(--rm-font-mono);
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--rm-muted);
  overflow-wrap: anywhere;
}

.buttons {
  display: flex;
  justify-content: flex-end;
  gap: var(--rm-space-2);
  padding-top: var(--rm-space-2);
  border-top: var(--rm-border-width) dotted var(--rm-line);
}

.drive {
  display: grid;
  grid-template-columns: minmax(0, 260px) minmax(0, 1fr) minmax(0, 330px);
  grid-template-areas: "tree main detail";
  gap: 18px;
  align-items: start;
}

.sidebar {
  grid-area: tree;
}

.content {
  grid-area: main;
}

.pane-detail {
  grid-area: detail;
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
  flex-wrap: wrap;
}

/* Only built where the tree can actually fold, which is the narrow layout. */
.fold {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--rm-ink);
  cursor: pointer;
}

.folded {
  display: none;
}

.folding {
  display: flex;
  flex-direction: column;
  gap: var(--rm-space-3);
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
  flex: none;
  width: 30px;
  height: 30px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 9px;
  background: var(--rm-lime);
  color: var(--rm-ink-on-bright);
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

.named {
  display: flex;
  align-items: center;
  gap: var(--rm-space-2);
  flex-wrap: wrap;
  min-width: 0;
}

.renaming,
.folderform {
  display: flex;
  flex-direction: column;
  gap: var(--rm-space-4);
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
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 290px), 1fr));
  gap: var(--rm-space-4);
}

/*
 * The header and the rows are separate grids, so the columns only line up if
 * both are told the same track widths: with `auto` they each sized to their own
 * contents and the headings drifted away from the switches they name, by a
 * whole word in Spanish. The tracks are declared once here and read by
 * DocumentRow.
 */
.table {
  --rm-doc-cols: minmax(80px, 1fr) 96px 120px;
  background: var(--rm-panel);
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: var(--rm-radius);
  box-shadow: var(--rm-lift) var(--rm-lift) 0 var(--rm-shadow);
  overflow: hidden;
}

.thead {
  display: grid;
  grid-template-columns: var(--rm-doc-cols);
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

/*
 * Three columns become two when the detail pane no longer has room to be a
 * column, and one when the tree stops being a margin and becomes a section of
 * its own. Below that the tree starts folded: on a phone the point of opening
 * the panel is the documents, and a full tree would push them off the screen.
 */
@media (max-width: 1240px) {
  .drive {
    grid-template-columns: minmax(0, 240px) minmax(0, 1fr);
    grid-template-areas:
      "tree main"
      "detail detail";
  }
}

@media (max-width: 900px) {
  .drive {
    grid-template-columns: minmax(0, 1fr);
    grid-template-areas:
      "tree"
      "main"
      "detail";
    gap: var(--rm-space-3);
  }

  .head {
    padding: var(--rm-space-3);
  }

  .sidebar,
  .placeholder {
    padding: var(--rm-space-3);
  }
}

@media (max-width: 600px) {
  .table {
    --rm-doc-cols: minmax(0, 1fr) 56px 104px;
  }

  .thead {
    gap: var(--rm-space-2);
    padding: 9px var(--rm-space-3);
  }
}
</style>
