<script setup lang="ts">
withDefaults(defineProps<{ tone?: 'info' | 'positive' | 'negative' }>(), { tone: 'info' })
</script>

<template>
  <p :class="['alert', tone]" role="status">
    <slot />
  </p>
</template>

<style scoped>
.alert {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-small);
}

.info {
  background: var(--accent-soft);
  color: var(--text);
}

.positive {
  background: var(--positive-soft);
  color: var(--positive);
}

.negative {
  background: var(--negative-soft);
  color: var(--negative);
}
</style>
