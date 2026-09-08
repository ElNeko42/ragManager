import { defineStore } from 'pinia'
import { ref } from 'vue'

import { readSession, signIn, signOut } from '../api/auth'
import type { Owner } from '../api/auth'

export const useSessionStore = defineStore('session', () => {
  const owner = ref<Owner | null>(null)
  const resolved = ref(false)

  /**
   * Asks the server who is signed in, once per page load.
   *
   * Every guarded route waits on this, so the answer is remembered rather than
   * asked again on each navigation.
   */
  async function ensureResolved(): Promise<void> {
    if (resolved.value) {
      return
    }
    try {
      owner.value = await readSession()
    } catch {
      owner.value = null
    } finally {
      resolved.value = true
    }
  }

  /**
   * Signs the owner in and keeps the resulting account.
   */
  async function logIn(email: string, password: string): Promise<void> {
    owner.value = await signIn(email, password)
    resolved.value = true
  }

  /**
   * Signs the owner out, forgetting the account even if the server errors.
   */
  async function logOut(): Promise<void> {
    try {
      await signOut()
    } finally {
      owner.value = null
      resolved.value = true
    }
  }

  /**
   * Forgets the account without calling the server.
   *
   * Used when a request comes back unauthorised, which means the session ended
   * somewhere else and the panel is holding a stale answer.
   */
  function forget(): void {
    owner.value = null
    resolved.value = true
  }

  return { owner, resolved, ensureResolved, logIn, logOut, forget }
})
