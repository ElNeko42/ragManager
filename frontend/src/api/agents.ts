import { request, requestAll, requestJson } from './client'

export interface Agent {
  agent_id: string
  name: string
  created_at: string
}

export interface AgentToken {
  token_id: string
  token_prefix: string
  created_at: string
  expires_at: string | null
  revoked_at: string | null
  is_active: boolean
}

export interface IssuedToken {
  token: string
  token_detail: AgentToken
}

export interface CreatedAgent extends IssuedToken {
  agent: Agent
}

/**
 * Returns every agent registered on this instance.
 */
export function listAgents(): Promise<Agent[]> {
  return requestAll<Agent>('/api/agents/')
}

/**
 * Registers an agent and mints its first token.
 *
 * The reply carries the token text, which the server never shows again, so
 * whatever calls this has to put it in front of the owner right away.
 */
export function createAgent(name: string, expiresAt: string | null): Promise<CreatedAgent> {
  return requestJson<CreatedAgent>('/api/agents/', 'POST', { name, expires_at: expiresAt })
}

/**
 * Deletes an agent along with its tokens and rules.
 */
export function deleteAgent(id: string): Promise<null> {
  return request<null>(`/api/agents/${id}/`, { method: 'DELETE' })
}

/**
 * Returns the tokens of one agent, without their secret text.
 */
export function listTokens(agentId: string): Promise<AgentToken[]> {
  return requestAll<AgentToken>(`/api/agents/${agentId}/tokens/`)
}

/**
 * Mints an extra token for an agent, returning its text once.
 */
export function issueToken(agentId: string, expiresAt: string | null): Promise<IssuedToken> {
  return requestJson<IssuedToken>(`/api/agents/${agentId}/tokens/`, 'POST', {
    expires_at: expiresAt
  })
}

/**
 * Revokes a token, which stops working immediately.
 */
export function revokeToken(agentId: string, tokenId: string): Promise<AgentToken> {
  return requestJson<AgentToken>(`/api/agents/${agentId}/tokens/${tokenId}/revoke/`, 'POST', {})
}
