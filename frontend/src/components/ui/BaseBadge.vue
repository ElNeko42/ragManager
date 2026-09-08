<script setup lang="ts">
withDefaults(defineProps<{ tone?: 'neutral' | 'positive' | 'negative' | 'warning' }>(), {
  tone: 'neutral'
})
</script>

<template>
  <span :class="['badge', tone]">
    <slot />
  </span>
</template>

<style scoped>
.badge {
  display: inline-block;
  padding: 1px var(--space-2);
  border-radius: 999px;
  font-size: 0.82em;
  font-weight: 600;
  white-space: nowrap;
}

.neutral {
  background: var(--surface-sunken);
  color: var(--text-muted);
  border: 1px solid var(--border);
}

.positive {
  background: var(--positive-soft);
  color: var(--positive);
}

.negative {
  background: var(--negative-soft);
  color: var(--negative);
}

.warning {
  background: var(--warning-soft);
  color: var(--warning);
}
</style>
