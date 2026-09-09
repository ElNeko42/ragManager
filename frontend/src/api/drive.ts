import { request, requestJson } from './client'

export type ProcessingStatus = 'pending' | 'processing' | 'ready' | 'failed' | null

export interface Folder {
  folder_id: string
  name: string
  parent: string | null
  collection: string
  is_root: boolean
  created_at: string
  updated_at: string
}

export interface Document {
  document_id: string
  folder: string
  name: string
  content_type: string
  size_bytes: number
  revision: number
  processing_status: ProcessingStatus
  is_agent_active: boolean
  chunk_count: number
  created_at: string
  updated_at: string
}

export interface DocumentDetail extends Document {
  last_error: string | null
}

export interface Collection {
  collection_id: string
  name: string
  provider: 'local' | 'api'
  base_url: string
  model_name: string
  vector_size: number
  is_default: boolean
  created_at: string
}

/**
 * Returns every folder, which is what the tree is built from.
 */
export function listFolders(): Promise<Folder[]> {
  return request<Folder[]>('/api/folders/')
}

/**
 * Creates a folder under a parent.
 */
export function createFolder(name: string, parent: string): Promise<Folder> {
  return requestJson<Folder>('/api/folders/', 'POST', { name, parent })
}

/**
 * Renames a folder or moves it under another parent.
 */
export function updateFolder(id: string, changes: Partial<Pick<Folder, 'name' | 'parent'>>) {
  return requestJson<Folder>(`/api/folders/${id}/`, 'PATCH', changes)
}

/**
 * Deletes a folder along with everything inside it.
 */
export function deleteFolder(id: string): Promise<null> {
  return request<null>(`/api/folders/${id}/`, { method: 'DELETE' })
}

/**
 * Returns the documents of one folder.
 */
export function listDocuments(folder: string): Promise<Document[]> {
  return request<Document[]>(`/api/documents/?folder=${encodeURIComponent(folder)}`)
}

/**
 * Returns one document with the reason its last processing run failed.
 */
export function readDocument(id: string): Promise<DocumentDetail> {
  return request<DocumentDetail>(`/api/documents/${id}/`)
}

/**
 * Stores a file in a folder.
 *
 * Nothing is queued for vectorising here: that starts when the agent flag is
 * switched on, so uploading never spends time on a file nobody asked agents
 * to read.
 */
export function uploadDocument(folder: string, file: File): Promise<Document> {
  const body = new FormData()
  body.append('file', file)
  body.append('folder', folder)
  return request<Document>('/api/documents/', { method: 'POST', body })
}

/**
 * Renames a document, moves it, or switches its agent flag.
 */
export function updateDocument(
  id: string,
  changes: { name?: string; folder?: string; is_agent_active?: boolean }
): Promise<Document> {
  return requestJson<Document>(`/api/documents/${id}/`, 'PATCH', changes)
}

/**
 * Deletes a document and the file behind it.
 */
export function deleteDocument(id: string): Promise<null> {
  return request<null>(`/api/documents/${id}/`, { method: 'DELETE' })
}

/**
 * Returns the address the browser downloads a document from.
 */
export function contentUrl(id: string): string {
  return `/api/documents/${id}/content/`
}

/**
 * Returns every collection, so a folder can show which model indexes it.
 */
export function listCollections(): Promise<Collection[]> {
  return request<Collection[]>('/api/collections/')
}
