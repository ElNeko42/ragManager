<script setup lang="ts">
export interface SelectOption {
  value: string
  label: string
}

withDefaults(
  defineProps<{ id: string; options: SelectOption[]; disabled?: boolean; placeholder?: string }>(),
  { disabled: false, placeholder: '' }
)

const model = defineModel<string>({ required: true })
</script>

<template>
  <select :id="id" v-model="model" class="select" :disabled="disabled">
    <option v-if="placeholder" value="">{{ placeholder }}</option>
    <option v-for="option in options" :key="option.value" :value="option.value">
      {{ option.label }}
    </option>
  </select>
</template>

<style scoped>
.select {
  width: 100%;
  padding: 10px var(--rm-space-3);
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 10px;
  background: var(--rm-panel);
  color: var(--rm-ink);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}

.select:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
