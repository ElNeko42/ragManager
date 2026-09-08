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
  gap: var(--space-2);
  margin: 0;
  color: var(--text-muted);
}

.dot {
  width: 10px;
  height: 10px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 700ms linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .dot {
    animation: none;
  }
}
</style>
