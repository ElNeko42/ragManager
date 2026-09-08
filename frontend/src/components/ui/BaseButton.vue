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
  gap: var(--rm-space-2);
  padding: 10px var(--rm-space-4);
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: var(--rm-radius-sm);
  font-weight: 700;
  cursor: pointer;
  transition: transform 90ms ease, box-shadow 90ms ease, background 90ms ease;
}

.button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.block {
  width: 100%;
}

.primary,
.secondary {
  box-shadow: 4px 4px 0 var(--rm-shadow);
}

.primary:hover:not(:disabled),
.secondary:hover:not(:disabled) {
  transform: translate(2px, 2px);
  box-shadow: 2px 2px 0 var(--rm-shadow);
}

.primary:active:not(:disabled),
.secondary:active:not(:disabled) {
  transform: translate(4px, 4px);
  box-shadow: 0 0 0 var(--rm-shadow);
}

.primary {
  background: var(--rm-lime);
  color: #17131f;
  font-family: var(--rm-font-display);
  font-size: 16px;
  letter-spacing: 0.02em;
}

.secondary {
  background: var(--rm-panel2);
  color: var(--rm-ink);
}

.quiet {
  padding: 6px 10px;
  border-style: dashed;
  border-color: var(--rm-line);
  border-radius: 999px;
  background: transparent;
  color: var(--rm-muted);
  font-weight: 400;
  font-size: 13px;
}

.quiet:hover:not(:disabled) {
  border-color: var(--rm-neg);
  color: var(--rm-neg);
}
</style>
