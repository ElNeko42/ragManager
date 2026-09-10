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

export interface AccountChange {
  current_password: string
  email?: string
  new_password?: string
}

/**
 * Changes the address or the password the owner signs in with.
 *
 * The current password travels with every change, including one that only
 * touches the address: the server asks for it, and an open browser is the
 * likeliest way someone else reaches this. Returns the updated account.
 */
export function updateAccount(change: AccountChange): Promise<Owner> {
  return requestJson<Owner>('/api/auth/account/', 'PATCH', change)
}

/**
 * Returns the owner behind the current session, or throws when there is none.
 */
export function readSession(): Promise<Owner> {
  return request<Owner>('/api/auth/session/')
}
