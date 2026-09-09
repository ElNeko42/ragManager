<script setup lang="ts">
defineProps<{ name: string; meta: string; hasChildren: boolean }>()
const emit = defineEmits<{ open: [] }>()
</script>

<template>
  <button type="button" class="card" @click="emit('open')">
    <span class="tab" aria-hidden="true" />
    <span class="naming">
      <strong>{{ name }}</strong>
      <span class="meta">{{ meta }}</span>
    </span>
    <span v-if="hasChildren" class="more" aria-hidden="true">▸</span>
  </button>
</template>

<style scoped>
.card {
  display: flex;
  align-items: center;
  gap: 11px;
  min-width: 0;
  padding: 13px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 14px;
  background: var(--rm-panel2);
  color: var(--rm-ink);
  text-align: left;
  cursor: pointer;
  box-shadow: 4px 4px 0 var(--rm-shadow);
  transition: transform 90ms ease, box-shadow 90ms ease, background 90ms ease;
}

.card:hover {
  background: var(--rm-cyan);
  color: #17131f;
  transform: translate(-1px, -1px);
  box-shadow: 6px 6px 0 var(--rm-shadow);
}

.tab {
  flex: none;
  width: 34px;
  height: 28px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 4px 9px 9px 9px;
  background: var(--rm-amber);
  box-shadow: inset 0 -3px 0 rgba(0, 0, 0, 0.14);
}

.naming {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.naming strong {
  font-size: 13.5px;
  line-height: 1.25;
  overflow-wrap: anywhere;
}

.meta {
  font-family: var(--rm-font-mono);
  font-size: 10px;
  opacity: 0.75;
}

.more {
  margin-left: auto;
  font-family: var(--rm-font-mono);
  font-size: 14px;
  opacity: 0.6;
}
</style>
