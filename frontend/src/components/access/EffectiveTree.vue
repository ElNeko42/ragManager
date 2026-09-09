<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import type { ResolvedFolder } from '../../api/access'

const props = defineProps<{ folders: ResolvedFolder[]; selected: string | null }>()
const emit = defineEmits<{ open: [id: string] }>()

const { t } = useI18n()
const collapsed = ref<Record<string, boolean>>({})

interface Row {
  id: string
  name: string
  depth: number
  allow: boolean
  source: string
  hasChildren: boolean
  collapsed: boolean
}

const rows = computed<Row[]>(() => {
  const out: Row[] = []
  const walk = (parent: string | null, depth: number) => {
    for (const folder of props.folders.filter((f) => f.parent === parent)) {
      const children = props.folders.filter((f) => f.parent === folder.folder_id)
      const shut = collapsed.value[folder.folder_id] === true
      out.push({
        id: folder.folder_id,
        name: folder.parent === null ? t('drive.everything') : folder.name,
        depth,
        allow: folder.effect === 'allow',
        source: t(`permissions.source.${folder.source}`),
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
        <span class="name">{{ row.name }}</span>
        <span class="verdicts">
          <span :class="['verdict', row.allow ? 'allow' : 'deny']">
            {{ row.allow ? t('permissions.allowed') : t('permissions.denied') }}
          </span>
          <span class="source">{{ row.source }}</span>
        </span>
      </button>
    </li>
  </ul>
</template>

<style scoped>
.rows {
  display: flex;
  flex-direction: column;
  gap: 4px;
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

.empty {
  color: var(--rm-line);
  cursor: default;
}

.node {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-width: 0;
  padding: 9px 11px;
  border: var(--rm-border-width) solid var(--rm-line);
  border-radius: var(--rm-radius-sm);
  background: var(--rm-panel2);
  color: var(--rm-ink);
  text-align: left;
  cursor: pointer;
}

.node:hover {
  border-color: var(--rm-border);
}

.on {
  border-color: var(--rm-border);
  background: var(--rm-cyan);
  color: #17131f;
  box-shadow: 3px 3px 0 var(--rm-shadow);
}

.name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}

.verdicts {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
}

.verdict {
  padding: 2px 8px;
  border-radius: 999px;
  font-family: var(--rm-font-mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  white-space: nowrap;
}

.allow {
  background: var(--rm-pos-soft);
  color: var(--rm-pos);
}

.deny {
  background: var(--rm-neg-soft);
  color: var(--rm-neg);
}

.on .verdict {
  border: var(--rm-border-width) solid #17131f;
}

.source {
  font-family: var(--rm-font-mono);
  font-size: 9.5px;
  color: var(--rm-muted);
}

.on .source {
  color: #17131f;
  opacity: 0.75;
}
</style>
