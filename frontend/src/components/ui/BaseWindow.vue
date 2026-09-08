<script setup lang="ts">
defineProps<{ title: string }>()
</script>

<template>
  <section class="window">
    <header class="chrome">
      <span class="dot pink" aria-hidden="true" />
      <span class="dot amber" aria-hidden="true" />
      <span class="dot lime" aria-hidden="true" />
      <span class="name">{{ title }}</span>
    </header>
    <div class="body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.window {
  background: var(--rm-panel);
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: var(--rm-radius);
  box-shadow: var(--rm-lift) var(--rm-lift) 0 var(--rm-shadow);
  overflow: hidden;
}

.chrome {
  display: flex;
  align-items: center;
  gap: var(--rm-space-2);
  padding: var(--rm-space-2) var(--rm-space-3);
  background: var(--rm-accent);
  border-bottom: var(--rm-border-width) solid var(--rm-border);
}

.dot {
  width: 11px;
  height: 11px;
  border: 1.5px solid var(--rm-border);
  border-radius: 50%;
}

.pink {
  background: var(--rm-pink);
}

.amber {
  background: var(--rm-amber);
}

.lime {
  background: var(--rm-lime);
}

.name {
  margin-left: var(--rm-space-1);
  font-family: var(--rm-font-mono);
  font-size: 11px;
  letter-spacing: 0.14em;
  color: var(--rm-accent-ink);
}

.body {
  padding: var(--rm-space-5) var(--rm-space-5) var(--rm-space-5);
}
</style>
