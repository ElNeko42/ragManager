<script setup lang="ts">
defineProps<{ label: string; forId: string; hint?: string }>()
</script>

<template>
  <div class="field">
    <label :for="forId">{{ label }}</label>
    <slot />
    <p v-if="hint" class="hint">{{ hint }}</p>
  </div>
</template>

<style scoped>
.field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

label {
  font-weight: 500;
  color: var(--text-muted);
}

.hint {
  margin: 0;
  font-size: 0.85em;
  color: var(--text-muted);
}
</style>
