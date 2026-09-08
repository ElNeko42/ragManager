<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'quiet'
    type?: 'button' | 'submit'
    disabled?: boolean
    block?: boolean
  }>(),
  { variant: 'secondary', type: 'button', disabled: false, block: false }
)
</script>

<template>
  <button :type="type" :disabled="disabled" :class="['button', variant, { block }]">
    <slot />
  </button>
</template>

<style scoped>
.button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  border: 1px solid transparent;
  border-radius: var(--radius-small);
  background: transparent;
  font-weight: 500;
  cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease;
}

.button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.block {
  width: 100%;
}

.primary {
  background: var(--accent);
  color: var(--accent-text);
}

.primary:hover:not(:disabled) {
  filter: brightness(1.08);
}

.secondary {
  background: var(--surface-raised);
  border-color: var(--border);
  color: var(--text);
}

.secondary:hover:not(:disabled) {
  background: var(--surface-sunken);
}

.quiet {
  color: var(--text-muted);
  padding: var(--space-1) var(--space-2);
}

.quiet:hover:not(:disabled) {
  color: var(--text);
}
</style>
