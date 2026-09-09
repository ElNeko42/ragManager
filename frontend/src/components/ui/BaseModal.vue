<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

defineProps<{ title: string; dismissible?: boolean }>()
const emit = defineEmits<{ close: [] }>()

const { t } = useI18n()
const panel = ref<HTMLElement | null>(null)

/**
 * Closes the dialog when the visitor presses escape.
 */
function onKey(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    emit('close')
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKey)
  panel.value?.focus()
})

onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="backdrop" @click.self="dismissible !== false && emit('close')">
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
        <button type="button" class="close" :aria-label="t('common.close')" @click="emit('close')">
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
  color: #17131f;
  font-size: 15px;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
}

.body {
  padding: 18px;
}
</style>
