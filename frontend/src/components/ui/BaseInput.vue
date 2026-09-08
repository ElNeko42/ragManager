<script setup lang="ts">
withDefaults(
  defineProps<{
    id: string
    type?: string
    autocomplete?: string
    required?: boolean
    disabled?: boolean
  }>(),
  { type: 'text', autocomplete: 'off', required: false, disabled: false }
)

const model = defineModel<string>({ required: true })
</script>

<template>
  <input
    :id="id"
    v-model="model"
    :type="type"
    :autocomplete="autocomplete"
    :required="required"
    :disabled="disabled"
  />
</template>

<style scoped>
input {
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-small);
  background: var(--surface);
  color: var(--text);
  width: 100%;
}

input:disabled {
  opacity: 0.6;
}
</style>
