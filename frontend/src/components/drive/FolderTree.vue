<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import BaseIcon from '../ui/BaseIcon.vue'
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
    <div class="finder">
      <BaseIcon name="search" :size="16" />
      <input
        v-model="query"
        type="search"
        class="filter"
        :placeholder="t('drive.filterFolders')"
        :aria-label="t('drive.filterFolders')"
      />
    </div>

    <ul class="rows">
      <li v-for="row in rows" :key="row.node.id" :style="{ paddingLeft: `${row.depth * 18}px` }">
        <button
          v-if="row.hasChildren"
          type="button"
          class="caret"
          :aria-expanded="!row.collapsed"
          :aria-label="`${row.collapsed ? t('common.expand') : t('common.collapse')} ${row.node.label}`"
          @click="fold(row.node.id)"
        >
          <BaseIcon :name="row.collapsed ? 'chevronRight' : 'chevronDown'" :size="16" />
        </button>
        <span v-else class="caret leaf" aria-hidden="true" />

        <button
          type="button"
          :class="['node', { on: row.node.id === selected }]"
          @click="emit('open', row.node.id)"
        >
          <BaseIcon
            :name="row.node.id === selected || (row.hasChildren && !row.collapsed) ? 'folderOpen' : 'folder'"
            :size="18"
          />
          <span class="label">{{ row.node.label }}</span>
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

.finder {
  display: flex;
  align-items: center;
  gap: var(--rm-space-2);
  padding: 0 10px;
  border: var(--rm-border-width) solid var(--rm-line);
  border-radius: 10px;
  background: var(--rm-panel2);
  color: var(--rm-muted);
}

.finder:focus-within {
  border-color: var(--rm-border);
  color: var(--rm-ink);
}

.filter {
  width: 100%;
  min-width: 0;
  padding: 9px 0;
  border: 0;
  background: transparent;
  color: var(--rm-ink);
  font-size: 13.5px;
}

.filter:focus {
  outline: none;
}

.filter::-webkit-search-cancel-button {
  cursor: pointer;
}

.rows {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin: 0;
  padding: 0;
  list-style: none;
}

li {
  display: flex;
  align-items: center;
  gap: 5px;
}

/*
 * The fold control is a button in its own right rather than a character in the
 * margin: at the size a caret glyph rendered, hitting it on a laptop trackpad
 * was a matter of luck, and on a touch screen it was below the size a finger
 * can aim at.
 */
.caret {
  display: grid;
  place-items: center;
  flex: none;
  width: 30px;
  height: 30px;
  padding: 0;
  border: var(--rm-border-width) solid var(--rm-line);
  border-radius: 9px;
  background: var(--rm-panel);
  color: var(--rm-ink);
  cursor: pointer;
  transition: background 90ms ease, border-color 90ms ease;
}

.caret:hover {
  border-color: var(--rm-border);
  background: var(--rm-pink);
  color: var(--rm-ink-on-bright);
}

.leaf {
  border-color: transparent;
  background: transparent;
  cursor: default;
}

.node {
  display: flex;
  align-items: center;
  gap: 9px;
  flex: 1;
  min-width: 0;
  padding: 9px 11px;
  border: var(--rm-border-width) solid transparent;
  border-radius: 10px;
  background: transparent;
  color: var(--rm-ink);
  font-size: 14px;
  text-align: left;
  cursor: pointer;
}

.node:hover {
  border-color: var(--rm-line);
  background: var(--rm-panel2);
}

.label {
  min-width: 0;
  overflow-wrap: anywhere;
}

.on {
  border-color: var(--rm-border);
  background: var(--rm-cyan);
  color: var(--rm-ink-on-bright);
  font-weight: 700;
  box-shadow: 2px 2px 0 var(--rm-shadow);
}
</style>
