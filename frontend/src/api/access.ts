import { request, requestJson } from './client'

export type Effect = 'allow' | 'deny'

export interface Permission {
  permission_id: string
  agent: string
  folder: string | null
  document: string | null
  effect: Effect
  created_at: string
}

export interface ResolvedFolder {
  folder_id: string
  name: string
  parent: string | null
  collection: string
  effect: Effect
  source: 'own' | 'inherited'
}

export interface ResolvedDocument {
  document_id: string
  name: string | null
  effect: Effect
}

export interface EffectiveAccess {
  folders: ResolvedFolder[]
  documents: ResolvedDocument[]
}

/**
 * Returns the rules written for one agent.
 */
export function listPermissions(agentId: string): Promise<Permission[]> {
  return request<Permission[]>(`/api/permissions/?agent=${encodeURIComponent(agentId)}`)
}

/**
 * Writes a rule over a folder for one agent.
 */
export function grantFolder(agent: string, folder: string, effect: Effect): Promise<Permission> {
  return requestJson<Permission>('/api/permissions/', 'POST', { agent, folder, effect })
}

/**
 * Flips an existing rule between allow and deny.
 */
export function setEffect(permissionId: string, effect: Effect): Promise<Permission> {
  return requestJson<Permission>(`/api/permissions/${permissionId}/`, 'PATCH', { effect })
}

/**
 * Removes a rule, which returns its target to whatever it inherits.
 */
export function removePermission(permissionId: string): Promise<null> {
  return request<null>(`/api/permissions/${permissionId}/`, { method: 'DELETE' })
}

/**
 * Returns what an agent actually reaches, with inheritance already resolved.
 *
 * The written rules are not the answer to what an agent sees: the nearest
 * ancestor holding a rule decides, and no rule anywhere means no access.
 */
export function readEffective(agentId: string): Promise<EffectiveAccess> {
  return request<EffectiveAccess>(`/api/permissions/effective/${agentId}/`)
}
