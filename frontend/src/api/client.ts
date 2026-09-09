let onUnauthorized: (() => void) | null = null

/**
 * Registers what to do when the server says the session is gone.
 *
 * A panel that keeps rendering after the session expired shows a page full of
 * stale data and fails every action, so one place decides what happens and
 * every request routes through it.
 */
export function handleUnauthorized(handler: () => void): void {
  onUnauthorized = handler
}

const CSRF_COOKIE = 'csrftoken'
const CSRF_ENDPOINT = '/api/auth/csrf/'

export class ApiError extends Error {
  readonly status: number
  readonly body: unknown

  constructor(status: number, body: unknown) {
    super(`The request failed with status ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

/**
 * Reads a cookie by name, or returns null when the browser has no such cookie.
 */
function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : null
}

/**
 * Returns the token the server expects on every request that changes state.
 *
 * Asks the server for one when this browser has none yet, which happens on a
 * first visit and after the cookie expires.
 */
async function resolveCsrfToken(): Promise<string> {
  const existing = readCookie(CSRF_COOKIE)
  if (existing) {
    return existing
  }
  await fetch(CSRF_ENDPOINT, { credentials: 'same-origin' })
  return readCookie(CSRF_COOKIE) ?? ''
}

/**
 * Sends a request to the API and returns its parsed body.
 *
 * Attaches the session cookie and, for anything other than a read, the token
 * that proves the request came from this panel. Throws ApiError carrying the
 * status and the parsed body, so callers can tell apart a rejected password
 * from a service that is down without matching on message text.
 */
export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase()
  const headers = new Headers(options.headers)
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json')
  }
  if (method !== 'GET' && method !== 'HEAD') {
    headers.set('X-CSRFToken', await resolveCsrfToken())
  }
  const response = await fetch(path, { ...options, headers, credentials: 'same-origin' })
  const body = await parseBody(response)
  if (!response.ok) {
    if (response.status === 401 && path !== '/api/auth/session/' && path !== '/api/auth/login/') {
      onUnauthorized?.()
    }
    throw new ApiError(response.status, body)
  }
  return body as T
}

/**
 * Sends a request whose body is JSON and returns the parsed answer.
 */
export async function requestJson<T>(
  path: string,
  method: string,
  payload: unknown
): Promise<T> {
  return request<T>(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
}

/**
 * Parses a response body, tolerating the empty ones the API returns on delete.
 */
async function parseBody(response: Response): Promise<unknown> {
  if (response.status === 204) {
    return null
  }
  const text = await response.text()
  if (!text) {
    return null
  }
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}
