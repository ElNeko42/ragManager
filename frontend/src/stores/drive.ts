import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import * as api from '../api/drive'
import type { Collection, Document, DocumentDetail, Folder } from '../api/drive'

export type Progress = 'ready' | 'processing' | 'pending' | 'failed' | 'never'

const POLL_MS = 4000

/**
 * Works out what the panel should say about a document.
 *
 * The stored status alone is misleading: a document that was indexed and then
 * switched off still has usable chunks, while one that was never switched on
 * was never queued at all. Returns the state to show.
 */
export function progressOf(document: Document): Progress {
  if (!document.is_agent_active) {
    return document.processing_status === 'ready' ? 'ready' : 'never'
  }
  return document.processing_status ?? 'pending'
}

export const useDriveStore = defineStore('drive', () => {
  const folders = ref<Folder[]>([])
  const collections = ref<Collection[]>([])
  const documents = ref<Document[]>([])
  const selected = ref<DocumentDetail | null>(null)
  const folderId = ref<string | null>(null)
  const loading = ref(false)
  const error = ref('')

  let timer: number | undefined

  const current = computed(() => folders.value.find((f) => f.folder_id === folderId.value) ?? null)
  const root = computed(() => folders.value.find((f) => f.is_root) ?? null)
  const children = computed(() => folders.value.filter((f) => f.parent === folderId.value))

  const collectionName = computed(() => {
    const id = current.value?.collection
    return collections.value.find((c) => c.collection_id === id)?.name ?? ''
  })

  const path = computed(() => {
    const chain: Folder[] = []
    let node = current.value
    while (node) {
      chain.unshift(node)
      node = folders.value.find((f) => f.folder_id === node?.parent) ?? null
    }
    return chain
  })

  const settling = computed(() =>
    documents.value.some((d) => {
      const state = progressOf(d)
      return state === 'pending' || state === 'processing'
    })
  )

  /**
   * Loads the tree and the collections, then opens a folder.
   */
  async function start(): Promise<void> {
    loading.value = true
    try {
      const [tree, cols] = await Promise.all([api.listFolders(), api.listCollections()])
      folders.value = tree
      collections.value = cols
      await open(folderId.value ?? tree.find((f) => f.is_root)?.folder_id ?? null)
    } catch {
      error.value = 'load'
    } finally {
      loading.value = false
    }
  }

  /**
   * Opens a folder and reads what it holds.
   */
  async function open(id: string | null): Promise<void> {
    folderId.value = id
    selected.value = null
    if (!id) {
      documents.value = []
      return
    }
    documents.value = await api.listDocuments(id)
    schedule()
  }

  /**
   * Re-reads the current folder without disturbing the selection.
   */
  async function refresh(): Promise<void> {
    if (!folderId.value) {
      return
    }
    documents.value = await api.listDocuments(folderId.value)
    if (selected.value) {
      selected.value = await api.readDocument(selected.value.document_id)
    }
    schedule()
  }

  /**
   * Keeps re-reading the folder while the queue still has work on it.
   *
   * The backend offers no push, so the panel asks again rather than leaving a
   * document stuck on "processing" until someone reloads the page. Polling
   * stops as soon as nothing is in flight.
   */
  function schedule(): void {
    window.clearTimeout(timer)
    if (settling.value) {
      timer = window.setTimeout(() => void refresh(), POLL_MS)
    }
  }

  /**
   * Stops the polling, so a closed panel makes no further requests.
   */
  function stop(): void {
    window.clearTimeout(timer)
  }

  /**
   * Reads the full card of one document.
   */
  async function select(id: string): Promise<void> {
    selected.value = await api.readDocument(id)
  }

  /**
   * Switches a document between hidden and readable by agents.
   */
  async function setActive(id: string, active: boolean): Promise<void> {
    const updated = await api.updateDocument(id, { is_agent_active: active })
    replace(updated)
    if (selected.value?.document_id === id) {
      selected.value = await api.readDocument(id)
    }
    schedule()
  }

  /**
   * Puts an updated document back in the list it came from.
   */
  function replace(updated: Document): void {
    documents.value = documents.value.map((d) =>
      d.document_id === updated.document_id ? updated : d
    )
  }

  /**
   * Stores files in the open folder, one after another.
   */
  async function upload(files: File[]): Promise<void> {
    if (!folderId.value) {
      return
    }
    for (const file of files) {
      await api.uploadDocument(folderId.value, file)
    }
    await refresh()
  }

  /**
   * Renames a document.
   */
  async function rename(id: string, name: string): Promise<void> {
    replace(await api.updateDocument(id, { name }))
    if (selected.value?.document_id === id) {
      selected.value = await api.readDocument(id)
    }
  }

  /**
   * Moves a document into another folder.
   */
  async function move(id: string, folder: string): Promise<void> {
    await api.updateDocument(id, { folder })
    await refresh()
  }

  /**
   * Deletes a document.
   */
  async function remove(id: string): Promise<void> {
    await api.deleteDocument(id)
    if (selected.value?.document_id === id) {
      selected.value = null
    }
    await refresh()
  }

  /**
   * Creates a folder inside the open one and moves into it.
   */
  async function addFolder(name: string): Promise<void> {
    if (!folderId.value) {
      return
    }
    const created = await api.createFolder(name, folderId.value)
    folders.value = [...folders.value, created]
    await open(created.folder_id)
  }

  /**
   * Renames a folder.
   */
  async function renameFolder(id: string, name: string): Promise<void> {
    const updated = await api.updateFolder(id, { name })
    folders.value = folders.value.map((f) => (f.folder_id === id ? updated : f))
  }

  /**
   * Deletes a folder and everything below it, then opens its parent.
   */
  async function removeFolder(id: string): Promise<void> {
    const parent = folders.value.find((f) => f.folder_id === id)?.parent ?? null
    await api.deleteFolder(id)
    folders.value = folders.value.filter((f) => f.folder_id !== id)
    await open(parent ?? root.value?.folder_id ?? null)
  }

  return {
    folders,
    collections,
    documents,
    selected,
    folderId,
    loading,
    error,
    current,
    root,
    children,
    collectionName,
    path,
    settling,
    start,
    open,
    refresh,
    stop,
    select,
    setActive,
    upload,
    rename,
    move,
    remove,
    addFolder,
    renameFolder,
    removeFolder
  }
})
