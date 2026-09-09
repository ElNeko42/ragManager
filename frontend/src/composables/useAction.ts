import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { describeError } from '../api/errors'

/**
 * Runs panel actions, reporting whether one is in flight and why one failed.
 *
 * Every view needs the same three things around a request, so they share one
 * implementation instead of three copies that drift apart. Returns the busy
 * flag, the failure message and the runner.
 */
export function useAction() {
  const { t } = useI18n()
  const busy = ref(false)
  const failure = ref('')

  /**
   * Runs one action, turning a rejection into a message the owner can read.
   */
  async function run(action: () => Promise<unknown>): Promise<void> {
    busy.value = true
    failure.value = ''
    try {
      await action()
    } catch (cause) {
      failure.value = describeError(cause, t)
    } finally {
      busy.value = false
    }
  }

  /**
   * Clears the current failure, so a retry starts from a clean slate.
   */
  function clear(): void {
    failure.value = ''
  }

  return { busy, failure, run, clear }
}
