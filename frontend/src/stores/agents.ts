import { defineStore } from 'pinia'
import { ref } from 'vue'

import * as api from '../api/agents'
import * as access from '../api/access'
import type { Agent, AgentToken } from '../api/agents'
import type { Permission } from '../api/access'

export interface AgentRow {
  agent: Agent
  tokens: AgentToken[]
  rules: Permission[]
}

export const useAgentsStore = defineStore('agents', () => {
  const rows = ref<AgentRow[]>([])
  const loading = ref(false)

  /**
   * Reads every agent with its tokens and its written rules.
   *
   * The three come from separate endpoints, so they are asked for together
   * rather than one card at a time.
   */
  async function load(): Promise<void> {
    loading.value = true
    try {
      const agents = await api.listAgents()
      rows.value = await Promise.all(
        agents.map(async (agent) => ({
          agent,
          tokens: await api.listTokens(agent.agent_id),
          rules: await access.listPermissions(agent.agent_id)
        }))
      )
    } finally {
      loading.value = false
    }
  }

  /**
   * Registers an agent and returns the one and only sight of its token.
   */
  async function create(name: string, expiresAt: string | null) {
    const created = await api.createAgent(name, expiresAt)
    await load()
    return created
  }

  /**
   * Mints an extra token for an agent and returns its text once.
   */
  async function issue(agentId: string, expiresAt: string | null) {
    const issued = await api.issueToken(agentId, expiresAt)
    await load()
    return issued
  }

  /**
   * Revokes a token, which stops working straight away.
   */
  async function revoke(agentId: string, tokenId: string): Promise<void> {
    await api.revokeToken(agentId, tokenId)
    await load()
  }

  /**
   * Deletes an agent along with its tokens and its rules.
   */
  async function remove(agentId: string): Promise<void> {
    await api.deleteAgent(agentId)
    await load()
  }

  return { rows, loading, load, create, issue, revoke, remove }
})
