import { onUnmounted, ref } from 'vue'

/**
 * Reports whether the window currently matches a media query, and keeps up.
 *
 * Layout belongs in the stylesheet, but a control that only exists at one size
 * has to be built or not built, not merely hidden: a button that does nothing
 * is still a stop on the way through the page for anyone using a keyboard or a
 * screen reader. Returns a boolean that changes with the window.
 */
export function useMediaQuery(query: string) {
  const list = window.matchMedia(query)
  const matches = ref(list.matches)

  /**
   * Keeps the answer in step with the window.
   */
  function update(event: MediaQueryListEvent): void {
    matches.value = event.matches
  }

  list.addEventListener('change', update)
  onUnmounted(() => list.removeEventListener('change', update))

  return matches
}
