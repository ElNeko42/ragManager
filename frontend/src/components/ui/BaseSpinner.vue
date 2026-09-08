<script setup lang="ts">
defineProps<{ label: string }>()
</script>

<template>
  <p class="spinner" role="status">
    <span class="dot" aria-hidden="true" />
    {{ label }}
  </p>
</template>

<style scoped>
.spinner {
  display: flex;
  align-items: center;
  gap: var(--rm-space-2);
  margin: 0;
  font-family: var(--rm-font-mono);
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--rm-muted);
}

.dot {
  width: 10px;
  height: 10px;
  border: 2px solid var(--rm-line);
  border-top-color: var(--rm-pink);
  border-radius: 50%;
  animation: rm-spin 700ms linear infinite;
}
</style>
