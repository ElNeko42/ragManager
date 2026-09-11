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
  if (payload === undefined) {
    return request<T>(path, { method })
  }
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

export interface Page<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

/**
 * Reads a listing that the server hands over one page at a time.
 *
 * The panel draws a whole folder tree and a whole folder at once, so it needs
 * every row rather than the first page; the server pages anyway, because an
 * instance holding thousands of documents cannot answer with all of them in
 * one go. Follows the links the server sends rather than counting pages
 * itself, so a row added between two requests cannot make it skip one.
 */
export async function requestAll<T>(path: string): Promise<T[]> {
  const rows: T[] = []
  let next: string | null = path
  while (next) {
    const page: Page<T> = await request<Page<T>>(next)
    rows.push(...page.results)
    next = page.next && samePathAndQuery(page.next)
  }
  return rows
}

/**
 * Reduces the link the server sent to a path this panel can ask for.
 *
 * The server builds that link from the host the request arrived on, which
 * behind a proxy is not always the host the browser is talking to. Only the
 * path and the query are ever needed, and keeping them relative means the
 * next page is fetched from wherever the panel itself was served.
 */
function samePathAndQuery(link: string): string {
  const parsed = new URL(link, window.location.origin)
  return `${parsed.pathname}${parsed.search}`
}
