<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useTree } from '../../composables/useTree'
import type { ResolvedFolder } from '../../api/access'

const props = defineProps<{ folders: ResolvedFolder[]; selected: string | null }>()
const emit = defineEmits<{ open: [id: string] }>()

const { t } = useI18n()

const nodes = computed(() =>
  props.folders.map((folder) => ({
    id: folder.folder_id,
    parent: folder.parent,
    label: folder.parent === null ? t('drive.everything') : folder.name,
    allow: folder.effect === 'allow',
    source: t(`permissions.source.${folder.source}`)
  }))
)

const { rows, fold } = useTree(nodes)
</script>

<template>
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
        <span class="name">{{ row.node.label }}</span>
        <span class="verdicts">
          <span :class="['verdict', row.node.allow ? 'allow' : 'deny']">
            {{ row.node.allow ? t('permissions.allowed') : t('permissions.denied') }}
          </span>
          <span class="source">{{ row.node.source }}</span>
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
