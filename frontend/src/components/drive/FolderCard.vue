<script setup lang="ts">
import { useI18n } from 'vue-i18n'

defineProps<{ name: string; meta: string; hasChildren: boolean; isRoot?: boolean }>()
const emit = defineEmits<{ open: []; rename: []; permissions: []; remove: [] }>()

const { t } = useI18n()
</script>

<template>
  <article class="card">
    <button type="button" class="open" @click="emit('open')">
      <span class="tab" aria-hidden="true" />
      <span class="naming">
        <strong>{{ name }}</strong>
        <span class="meta">{{ meta }}</span>
      </span>
      <span v-if="hasChildren" class="more" aria-hidden="true">▸</span>
    </button>

    <div class="tools">
      <button
        type="button"
        class="tool"
        :title="t('drive.renameFolder')"
        :aria-label="`${t('drive.renameFolder')}: ${name}`"
        @click="emit('rename')"
      >
        {{ t('drive.renameShort') }}
      </button>
      <button
        type="button"
        class="tool"
        :title="t('drive.folderPermissions')"
        :aria-label="`${t('drive.folderPermissions')}: ${name}`"
        @click="emit('permissions')"
      >
        {{ t('drive.permissionsShort') }}
      </button>
      <button
        v-if="!isRoot"
        type="button"
        class="tool danger"
        :title="t('drive.deleteFolder')"
        :aria-label="`${t('drive.deleteFolder')}: ${name}`"
        @click="emit('remove')"
      >
        {{ t('drive.deleteShort') }}
      </button>
    </div>
  </article>
</template>

<style scoped>
.card {
  display: flex;
  flex-direction: column;
  min-width: 0;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 14px;
  background: var(--rm-panel2);
  box-shadow: 4px 4px 0 var(--rm-shadow);
  transition: transform 90ms ease, box-shadow 90ms ease;
}

.card:hover {
  transform: translate(-1px, -1px);
  box-shadow: 6px 6px 0 var(--rm-shadow);
}

.open {
  display: flex;
  align-items: center;
  gap: 11px;
  min-width: 0;
  padding: 13px;
  border: 0;
  border-radius: 12px 12px 0 0;
  background: transparent;
  color: var(--rm-ink);
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.open:hover {
  background: var(--rm-cyan);
  color: #17131f;
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
  font-size: 10.5px;
  color: var(--rm-muted);
}

.open:hover .meta {
  color: #17131f;
}

.more {
  margin-left: auto;
  font-family: var(--rm-font-mono);
  font-size: 12px;
}

.tools {
  display: flex;
  gap: 6px;
  padding: 8px 10px;
  border-top: var(--rm-border-width) dotted var(--rm-line);
}

.tool {
  padding: 4px 10px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 999px;
  background: var(--rm-panel);
  color: var(--rm-ink);
  font-family: var(--rm-font-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  cursor: pointer;
}

.tool:hover {
  background: var(--rm-lime);
  color: #17131f;
}

.danger:hover {
  background: var(--rm-pink);
}
</style>
