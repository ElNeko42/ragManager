import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import type { Ref } from 'vue'

/**
 * Reports whether an element's contents have stopped fitting across it.
 *
 * A width in a media query is a guess about how wide a word is, and the guess
 * is wrong as soon as the language changes: the same bar that fits in English
 * spills in Spanish, where every label is longer. Measuring the bar itself is
 * the same decision made from the answer rather than from an estimate of it,
 * and it holds for a language nobody has added yet.
 *
 * The element must be laid out so that contents which do not fit overflow it,
 * rather than wrapping or shrinking, or there is nothing to measure. Returns
 * the answer and a way to ask again.
 */
export function useTooTight(target: Ref<HTMLElement | null>) {
  const tight = ref(false)
  let settling = false
  let asked = false

  /**
   * Measures the element with everything shown, then decides.
   *
   * Measuring while the contents are already folded away would only ever
   * confirm the fold, so they are put back first and the answer taken from
   * the full width. The frame that follows is left alone: the observer that
   * calls this fires again on the change this makes, and answering that would
   * be measuring in a circle.
   */
  async function measure(): Promise<void> {
    if (settling) {
      asked = true
      return
    }
    const el = target.value
    if (!el) {
      return
    }
    settling = true
    if (tight.value) {
      tight.value = false
      await nextTick()
    }
    tight.value = el.scrollWidth > el.clientWidth
    await nextTick()
    requestAnimationFrame(() => {
      settling = false
      if (asked) {
        asked = false
        void measure()
      }
    })
  }

  let observer: ResizeObserver | null = null

  onMounted(() => {
    observer = new ResizeObserver(() => void measure())
    if (target.value) {
      observer.observe(target.value)
    }
    void measure()
    // A word in the fallback font is not the width it will be once the real
    // one arrives, so the question is asked again when it does.
    void document.fonts?.ready.then(() => measure())
  })

  onUnmounted(() => observer?.disconnect())

  return { tight, measure }
}
