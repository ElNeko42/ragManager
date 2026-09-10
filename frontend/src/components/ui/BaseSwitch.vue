<script setup lang="ts">
defineProps<{ label: string; disabled?: boolean }>()
const model = defineModel<boolean>({ required: true })
</script>

<template>
  <button
    type="button"
    role="switch"
    :aria-checked="model"
    :aria-label="label"
    :disabled="disabled"
    :class="['track', { on: model }]"
    @click.stop="model = !model"
  >
    <span class="knob" aria-hidden="true" />
  </button>
</template>

<style scoped>
.track {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  flex: none;
  width: 46px;
  height: 24px;
  padding: 2px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 999px;
  background: var(--rm-panel2);
  cursor: pointer;
  transition: background 120ms ease;
}

.track:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.on {
  background: var(--rm-lime);
}

/*
 * The knob slides on a transform. Moving it by switching justify-content put it
 * at the far end in a single frame, which read as a glitch rather than as a
 * switch being thrown.
 */
.knob {
  width: 16px;
  height: 16px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 50%;
  background: var(--rm-panel);
  transition: transform 120ms ease;
}

.on .knob {
  transform: translateX(22px);
}
</style>
