/**
 * Renders a byte count the way a person reads it.
 */
export function formatBytes(value: number): string {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)} MB`
  }
  if (value >= 1000) {
    return `${Math.round(value / 1000)} KB`
  }
  return `${value} B`
}

/**
 * Returns the extension badge of a file name.
 *
 * Falls back to a fixed word rather than an empty box, since a name with no
 * extension still needs something to show in the card.
 */
export function formatExtension(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot === -1 ? 'BIN' : name.slice(dot + 1).toUpperCase().slice(0, 4)
}

/**
 * Renders a timestamp as the day it happened.
 */
export function formatDate(value: string): string {
  return value.slice(0, 10)
}
