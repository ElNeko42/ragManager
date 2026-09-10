<script setup lang="ts">
import { onBeforeUnmount, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { onBeforeRouteLeave } from 'vue-router'

const props = defineProps<{ dirty: boolean }>()

const { t } = useI18n()

/**
 * Asks the browser to check before it throws the page away.
 *
 * Reloading, closing the tab or following a link out of the panel all destroy
 * whatever was typed and none of them can be undone. The browser shows its own
 * wording here and refuses to let a page choose it, which is deliberate: a page
 * that could write this text could use it to frighten people into staying. The
 * message is still handed over because a browser old enough to read it treats
 * an empty one as permission to say nothing at all.
 */
function warnBeforeUnload(event: BeforeUnloadEvent): void {
  event.preventDefault()
  event.returnValue = t('common.unsavedChanges')
}

/**
 * Starts or stops listening, so a clean form never interrupts anyone.
 */
function listen(dirty: boolean): void {
  window.removeEventListener('beforeunload', warnBeforeUnload)
  if (dirty) {
    window.addEventListener('beforeunload', warnBeforeUnload)
  }
}

watch(() => props.dirty, listen, { immediate: true })

onBeforeUnmount(() => listen(false))

onBeforeRouteLeave(() => {
  if (!props.dirty) {
    return true
  }
  return window.confirm(t('common.unsavedChanges'))
})
</script>

<template>
  <span class="guard" aria-hidden="true" />
</template>

<style scoped>
.guard {
  display: none;
}
</style>
