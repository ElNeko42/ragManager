<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import type { Folder } from '../../api/drive'

const props = defineProps<{ folders: Folder[]; selected: string | null }>()
const emit = defineEmits<{ open: [id: string] }>()

const { t } = useI18n()
const query = ref('')
const collapsed = ref<Record<string, boolean>>({})

interface Row {
  id: string
  name: string
  depth: number
  hasChildren: boolean
  collapsed: boolean
}

/**
 * Names the root by what it holds rather than by its stored slug.
 */
function labelOf(folder: Folder): string {
  return folder.is_root ? t('drive.everything') : folder.name
}

/**
 * Reports whether a folder or anything below it matches the filter.
 *
 * A branch is kept when a descendant matches, so filtering never hides the
 * path that leads to a hit.
 */
function branchMatches(folder: Folder, needle: string): boolean {
  if (labelOf(folder).toLowerCase().includes(needle)) {
    return true
  }
  return props.folders
    .filter((f) => f.parent === folder.folder_id)
    .some((child) => branchMatches(child, needle))
}

const rows = computed<Row[]>(() => {
  const needle = query.value.trim().toLowerCase()
  const out: Row[] = []
  const walk = (parent: string | null, depth: number) => {
    for (const folder of props.folders.filter((f) => f.parent === parent)) {
      if (needle && !branchMatches(folder, needle)) {
        continue
      }
      const children = props.folders.filter((f) => f.parent === folder.folder_id)
      const shut = !needle && collapsed.value[folder.folder_id] === true
      out.push({
        id: folder.folder_id,
        name: labelOf(folder),
        depth,
        hasChildren: children.length > 0,
        collapsed: shut
      })
      if (!shut) {
        walk(folder.folder_id, depth + 1)
      }
    }
  }
  walk(null, 0)
  return out
})

/**
 * Folds or unfolds one branch of the tree.
 */
function fold(id: string): void {
  collapsed.value = { ...collapsed.value, [id]: !collapsed.value[id] }
}
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
      <li v-for="row in rows" :key="row.id" :style="{ paddingLeft: `${row.depth * 16}px` }">
        <button
          v-if="row.hasChildren"
          type="button"
          class="caret"
          :aria-expanded="!row.collapsed"
          :aria-label="row.name"
          @click="fold(row.id)"
        >
          {{ row.collapsed ? '▸' : '▾' }}
        </button>
        <span v-else class="caret empty" aria-hidden="true">·</span>

        <button
          type="button"
          :class="['node', { on: row.id === selected }]"
          @click="emit('open', row.id)"
        >
          {{ row.name }}
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
