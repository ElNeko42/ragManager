<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useTree } from '../../composables/useTree'
import type { Folder } from '../../api/drive'

const props = defineProps<{ folders: Folder[]; selected: string | null }>()
const emit = defineEmits<{ open: [id: string] }>()

const { t } = useI18n()
const query = ref('')

const needle = computed(() => query.value.trim().toLowerCase())

/**
 * Names the root by what it holds rather than by its stored slug.
 */
function labelOf(folder: Folder): string {
  return folder.is_root ? t('drive.everything') : folder.name
}

const nodes = computed(() =>
  props.folders.map((folder) => ({
    id: folder.folder_id,
    parent: folder.parent,
    label: labelOf(folder)
  }))
)

const { rows, fold } = useTree(nodes, {
  keep: (node) => !needle.value || node.label.toLowerCase().includes(needle.value),
  expandAll: () => needle.value !== ''
})
</script>

<template>
  <div class="tree">
    <input
      v-model="query"
      type="search"
      class="filter"
      :placeholder="t('drive.filterFolders')"
      :aria-label="t('drive.filterFolders')"
    />

    <ul class="rows">
      <li v-for="row in rows" :key="row.node.id" :style="{ paddingLeft: `${row.depth * 16}px` }">
        <button
          v-if="row.hasChildren"
          type="button"
          class="caret"
          :aria-expanded="!row.collapsed"
          :aria-label="`${row.collapsed ? t('common.expand') : t('common.collapse')} ${row.node.label}`"
          @click="fold(row.node.id)"
        >
          {{ row.collapsed ? '▸' : '▾' }}
        </button>
        <span v-else class="caret empty" aria-hidden="true">·</span>

        <button
          type="button"
          :class="['node', { on: row.node.id === selected }]"
          @click="emit('open', row.node.id)"
        >
          {{ row.node.label }}
        </button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.tree {
  display: flex;
  flex-direction: column;
  gap: var(--rm-space-3);
}

.filter {
  width: 100%;
  padding: 7px 10px;
  border: var(--rm-border-width) solid var(--rm-line);
  border-radius: 9px;
  background: var(--rm-panel2);
  color: var(--rm-ink);
  font-size: 12.5px;
}

.filter:focus {
  outline: none;
  border-color: var(--rm-border);
}

.rows {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 0;
  padding: 0;
  list-style: none;
}

li {
  display: flex;
  align-items: stretch;
}

.caret {
  flex: none;
  width: 20px;
  display: grid;
  place-items: center;
  border: 0;
  background: transparent;
  color: var(--rm-muted);
  font-family: var(--rm-font-mono);
  font-size: 11px;
  cursor: pointer;
}

.caret:hover {
  color: var(--rm-pink);
}

.empty {
  color: var(--rm-line);
  cursor: default;
}

.node {
  flex: 1;
  min-width: 0;
  padding: 6px 10px;
  border: var(--rm-border-width) solid transparent;
  border-radius: 9px;
  background: transparent;
  color: var(--rm-ink);
  text-align: left;
  overflow-wrap: anywhere;
  cursor: pointer;
}

.node:hover {
  border-color: var(--rm-line);
  background: var(--rm-panel2);
}

.on {
  border-color: var(--rm-border);
  background: var(--rm-cyan);
  color: #17131f;
  font-weight: 700;
}
</style>
