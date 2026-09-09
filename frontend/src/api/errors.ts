import { ApiError } from './client'

type Translate = (key: string) => string

/**
 * Turns a failed request into a sentence the owner can act on.
 *
 * Takes the thrown cause and a translator. Collapsing every failure into one
 * generic line hides the difference between a name already taken, a file over
 * the limit and a server that is simply down, which are three different things
 * to do next. The body is read when the API sent a field message, because that
 * is more precise than anything chosen from the status alone. Returns the
 * message to show.
 */
export function describeError(cause: unknown, t: Translate): string {
  if (!(cause instanceof ApiError)) {
    return t('errors.unreachable')
  }
  const detail = fieldMessage(cause.body)
  if (cause.status === 400 && detail) {
    return detail
  }
  const byStatus: Record<number, string> = {
    400: 'errors.rejected',
    401: 'errors.signedOut',
    403: 'errors.forbidden',
    404: 'errors.missing',
    409: 'errors.conflict',
    411: 'errors.noLength',
    413: 'errors.tooLarge',
    429: 'errors.throttled',
    503: 'errors.unavailable'
  }
  const key = byStatus[cause.status]
  if (key) {
    return detail && cause.status !== 401 ? `${t(key)} ${detail}` : t(key)
  }
  return detail || t('errors.unexpected')
}

/**
 * Digs the human sentence out of a rejection body.
 *
 * The API answers either with a detail line or with one message per field, so
 * both shapes are unwrapped rather than shown as raw JSON.
 */
function fieldMessage(body: unknown): string {
  if (typeof body === 'string') {
    return body
  }
  if (!body || typeof body !== 'object') {
    return ''
  }
  const parts: string[] = []
  for (const value of Object.values(body as Record<string, unknown>)) {
    if (typeof value === 'string') {
      parts.push(value)
    } else if (Array.isArray(value)) {
      parts.push(...value.filter((item): item is string => typeof item === 'string'))
    }
  }
  return parts.join(' ')
}
