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
.segmented {
  display: flex;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 999px;
  overflow: hidden;
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

button:hover {
  color: var(--rm-ink);
}

.on {
  background: var(--rm-pink);
  color: #17131f;
  font-weight: 700;
}
</style>
