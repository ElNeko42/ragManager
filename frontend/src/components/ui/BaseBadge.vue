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
  padding: 3px 9px;
  border-radius: 999px;
  font-family: var(--rm-font-mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  white-space: nowrap;
}

.neutral {
  border: var(--rm-border-width) solid var(--rm-line);
  background: var(--rm-panel2);
  color: var(--rm-muted);
}

.positive {
  border: var(--rm-border-width) solid var(--rm-border);
  background: var(--rm-pos-soft);
  color: var(--rm-pos);
}

.negative {
  border: var(--rm-border-width) solid var(--rm-border);
  background: var(--rm-neg-soft);
  color: var(--rm-neg);
}

.warning {
  border: var(--rm-border-width) solid var(--rm-border);
  background: var(--rm-warn-soft);
  color: var(--rm-warn);
}
</style>
