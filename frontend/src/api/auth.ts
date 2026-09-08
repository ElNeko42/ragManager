import { request, requestJson } from './client'

export interface Owner {
  user_id: string
  email: string
}

/**
 * Opens a session for the owner and returns the account behind it.
 */
export function signIn(email: string, password: string): Promise<Owner> {
  return requestJson<Owner>('/api/auth/login/', 'POST', { email, password })
}

/**
 * Closes the current session.
 */
export function signOut(): Promise<null> {
  return request<null>('/api/auth/logout/', { method: 'POST' })
}

/**
 * Returns the owner behind the current session, or throws when there is none.
 */
export function readSession(): Promise<Owner> {
  return request<Owner>('/api/auth/session/')
}
