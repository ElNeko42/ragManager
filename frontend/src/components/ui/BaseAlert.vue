<script setup lang="ts">
withDefaults(defineProps<{ tone?: 'info' | 'positive' | 'negative' }>(), { tone: 'info' })
</script>

<template>
  <p :class="['alert', tone]" role="status">
    <span class="beat" aria-hidden="true" />
    <slot />
  </p>
</template>

<style scoped>
.alert {
  display: flex;
  align-items: center;
  gap: var(--rm-space-3);
  margin: 0;
  padding: var(--rm-space-3) var(--rm-space-4);
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 14px;
  font-family: var(--rm-font-display);
  font-size: 16px;
  font-weight: 700;
}

.beat {
  flex: none;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: currentColor;
}

.info {
  background: var(--rm-panel2);
  color: var(--rm-ink);
}

.positive {
  background: var(--rm-pos-soft);
  color: var(--rm-pos);
}

.positive .beat {
  animation: rm-blink 1.6s ease-in-out infinite;
}

.negative {
  background: var(--rm-neg-soft);
  color: var(--rm-neg);
}
</style>
