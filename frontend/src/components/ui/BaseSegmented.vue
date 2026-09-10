<script setup lang="ts">
export interface Segment {
  value: string
  label: string
}

defineProps<{ segments: Segment[]; label: string }>()
const model = defineModel<string>({ required: true })
</script>

<template>
  <div class="segmented" role="group" :aria-label="label">
    <button
      v-for="segment in segments"
      :key="segment.value"
      type="button"
      :class="{ on: model === segment.value }"
      :aria-pressed="model === segment.value"
      @click="model = segment.value"
    >
      {{ segment.label }}
    </button>
  </div>
</template>

<style scoped>
/*
 * The ends are rounded on the buttons themselves rather than by clipping the
 * group: an overflow that hides the corners hides the focus ring with them,
 * which left the language and view switchers untrackable from the keyboard.
 */
.segmented {
  display: flex;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 999px;
  background: var(--rm-panel2);
  font-family: var(--rm-font-mono);
  font-size: 11px;
  letter-spacing: 0.1em;
}

button {
  padding: 5px 11px;
  border: 0;
  background: var(--rm-panel2);
  color: var(--rm-muted);
  cursor: pointer;
}

button:first-child {
  border-radius: 999px 0 0 999px;
  padding-left: 13px;
}

button:last-child {
  border-radius: 0 999px 999px 0;
  padding-right: 13px;
}

button:only-child {
  border-radius: 999px;
}

button + button {
  border-left: var(--rm-border-width) solid var(--rm-border);
}

button:hover:not(.on) {
  color: var(--rm-ink);
}

.on {
  background: var(--rm-pink);
  color: var(--rm-ink-on-bright);
  font-weight: 700;
}
</style>
