<script setup lang="ts">
defineProps<{ title?: string; subtitle?: string }>()
</script>

<template>
  <section class="card">
    <header v-if="title || $slots.actions" class="head">
      <div>
        <h2 v-if="title">{{ title }}</h2>
        <p v-if="subtitle" class="subtitle">{{ subtitle }}</p>
      </div>
      <div v-if="$slots.actions" class="actions">
        <slot name="actions" />
      </div>
    </header>
    <slot />
  </section>
</template>

<style scoped>
.card {
  display: flex;
  flex-direction: column;
  gap: var(--rm-space-4);
  padding: var(--rm-space-5);
  background: var(--rm-panel);
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: var(--rm-radius);
  box-shadow: var(--rm-lift) var(--rm-lift) 0 var(--rm-shadow);
}

.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--rm-space-4);
  flex-wrap: wrap;
}

h2 {
  font-size: 22px;
}

.subtitle {
  margin: var(--rm-space-1) 0 0;
  color: var(--rm-muted);
}

.actions {
  display: flex;
  gap: var(--rm-space-2);
}
</style>
