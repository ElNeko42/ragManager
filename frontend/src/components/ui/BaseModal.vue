<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{ title: string; dismissible?: boolean }>()
const emit = defineEmits<{ close: [] }>()

const { t } = useI18n()
const panel = ref<HTMLElement | null>(null)

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * Reports whether the visitor is allowed to walk away from this dialog.
 *
 * A dialog that shows something the server will never show again, such as a
 * freshly issued token, opts out: losing it to a stray keystroke means issuing
 * a new one.
 */
function canDismiss(): boolean {
  return props.dismissible !== false
}

/**
 * Handles escape to leave and tab to stay inside the dialog.
 */
function onKey(event: KeyboardEvent): void {
  if (event.key === 'Escape' && canDismiss()) {
    emit('close')
    return
  }
  if (event.key !== 'Tab' || !panel.value) {
    return
  }
  const stops = Array.from(panel.value.querySelectorAll<HTMLElement>(FOCUSABLE))
  if (stops.length === 0) {
    event.preventDefault()
    panel.value.focus()
    return
  }
  const first = stops[0]
  const last = stops[stops.length - 1]
  const active = document.activeElement
  if (event.shiftKey && (active === first || active === panel.value)) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && active === last) {
    event.preventDefault()
    first.focus()
  }
}

let restoreOverflow = ''
let opener: HTMLElement | null = null

onMounted(() => {
  opener = document.activeElement instanceof HTMLElement ? document.activeElement : null
  restoreOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  window.addEventListener('keydown', onKey)
  panel.value?.focus()
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKey)
  document.body.style.overflow = restoreOverflow
  opener?.focus()
})
</script>

<template>
  <div class="backdrop" @click.self="canDismiss() && emit('close')">
    <section
      ref="panel"
      class="panel"
      role="dialog"
      aria-modal="true"
      :aria-label="title"
      tabindex="-1"
    >
      <header class="chrome">
        <span class="dot pink" aria-hidden="true" />
        <span class="dot amber" aria-hidden="true" />
        <span class="dot lime" aria-hidden="true" />
        <span class="name">{{ title }}</span>
        <button
          v-if="canDismiss()"
          type="button"
          class="close"
          :aria-label="t('common.close')"
          @click="emit('close')"
        >
          ×
        </button>
      </header>
      <div class="body">
        <slot />
      </div>
    </section>
  </div>
</template>

<style scoped>
.backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--rm-space-5);
  background: rgba(11, 8, 20, 0.55);
}

.panel {
  width: 100%;
  max-width: 560px;
  max-height: 86vh;
  overflow: auto;
  background: var(--rm-panel);
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 18px;
  box-shadow: 8px 8px 0 var(--rm-shadow);
}

.chrome {
  position: sticky;
  top: 0;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: var(--rm-space-2);
  padding: var(--rm-space-2) var(--rm-space-3);
  background: var(--rm-accent);
  border-bottom: var(--rm-border-width) solid var(--rm-border);
}

.dot {
  width: 11px;
  height: 11px;
  border: 1.5px solid var(--rm-border);
  border-radius: 50%;
}

.pink {
  background: var(--rm-pink);
}

.amber {
  background: var(--rm-amber);
}

.lime {
  background: var(--rm-lime);
}

.name {
  margin-left: var(--rm-space-1);
  margin-right: auto;
  font-family: var(--rm-font-mono);
  font-size: 11px;
  letter-spacing: 0.14em;
  color: var(--rm-accent-ink);
}

.close {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 50%;
  background: var(--rm-pink);
  color: var(--rm-ink-on-bright);
  font-size: 15px;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
}

.body {
  padding: 18px;
}

@media (max-width: 600px) {
  .backdrop {
    padding: var(--rm-space-3);
  }

  .panel {
    max-height: 92vh;
  }

  .body {
    padding: var(--rm-space-3);
  }
}
</style>
