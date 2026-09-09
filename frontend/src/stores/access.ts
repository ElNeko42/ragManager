import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import * as api from '../api/access'
import { listAgents } from '../api/agents'
import type { Agent } from '../api/agents'
import type { Effect, EffectiveAccess, Permission, ResolvedFolder } from '../api/access'

export const useAccessStore = defineStore('access', () => {
  const agents = ref<Agent[]>([])
  const agentId = ref<string | null>(null)
  const effective = ref<EffectiveAccess | null>(null)
  const rules = ref<Permission[]>([])
  const folderId = ref<string | null>(null)
  const loading = ref(false)

  const agent = computed(() => agents.value.find((a) => a.agent_id === agentId.value) ?? null)
  const folders = computed<ResolvedFolder[]>(() => effective.value?.folders ?? [])
  const folder = computed(() => folders.value.find((f) => f.folder_id === folderId.value) ?? null)

  const reachable = computed(() => folders.value.filter((f) => f.effect === 'allow').length)

  const ownRule = computed(() =>
    rules.value.find((rule) => rule.folder === folderId.value && rule.document === null)
  )

  const path = computed(() => {
    const chain: ResolvedFolder[] = []
    let node = folder.value
    while (node) {
      chain.unshift(node)
      node = folders.value.find((f) => f.folder_id === node?.parent) ?? null
    }
    return chain
  })

  /**
   * Loads the agents and opens the one asked for, or the first there is.
   *
   * A folder can be asked for as well, because the owner often arrives here
   * from a folder in the drive wanting to decide that one folder, and having
   * to find it again in the tree is work the link can do.
   */
  async function load(preferred?: string | null, folder?: string | null): Promise<void> {
    loading.value = true
    try {
      agents.value = await listAgents()
      if (folder) {
        folderId.value = folder
      }
      const wanted = preferred ?? agentId.value ?? agents.value[0]?.agent_id ?? null
      await pick(wanted)
    } finally {
      loading.value = false
    }
  }

  /**
   * Switches to one agent and resolves what it reaches.
   */
  async function pick(id: string | null): Promise<void> {
    agentId.value = id
    if (!id) {
      effective.value = null
      rules.value = []
      return
    }
    const [resolved, written] = await Promise.all([
      api.readEffective(id),
      api.listPermissions(id)
    ])
    effective.value = resolved
    rules.value = written
    if (!resolved.folders.some((f) => f.folder_id === folderId.value)) {
      folderId.value = resolved.folders.find((f) => f.parent === null)?.folder_id ?? null
    }
  }

  /**
   * Re-reads the current agent after a rule changed.
   */
  async function refresh(): Promise<void> {
    await pick(agentId.value)
  }

  /**
   * Writes or flips the rule on the open folder.
   *
   * An agent may hold only one rule per target, so an existing rule is
   * changed rather than a second one written beside it.
   */
  async function setRule(effect: Effect): Promise<void> {
    if (!agentId.value || !folderId.value) {
      return
    }
    const existing = ownRule.value
    if (existing) {
      await api.setEffect(existing.permission_id, effect)
    } else {
      await api.grantFolder(agentId.value, folderId.value, effect)
    }
    await refresh()
  }

  /**
   * Drops the rule on the open folder, returning it to what it inherits.
   */
  async function clearRule(): Promise<void> {
    const existing = ownRule.value
    if (!existing) {
      return
    }
    await api.removePermission(existing.permission_id)
    await refresh()
  }

  return {
    agents,
    agentId,
    effective,
    rules,
    folderId,
    loading,
    agent,
    folders,
    folder,
    reachable,
    ownRule,
    path,
    load,
    pick,
    refresh,
    setRule,
    clearRule
  }
})
