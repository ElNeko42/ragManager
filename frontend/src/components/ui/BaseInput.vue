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
  width: 100%;
  padding: 11px 13px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 10px;
  background: var(--rm-panel2);
  color: var(--rm-ink);
}

input:focus {
  outline: none;
  background: var(--rm-panel);
  box-shadow: 3px 3px 0 var(--rm-shadow);
}

input:disabled {
  opacity: 0.6;
}
</style>
