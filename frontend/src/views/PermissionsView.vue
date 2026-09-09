<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import AppShell from '../components/layout/AppShell.vue'
import BaseAlert from '../components/ui/BaseAlert.vue'
import BaseButton from '../components/ui/BaseButton.vue'
import BaseSpinner from '../components/ui/BaseSpinner.vue'
import EffectiveTree from '../components/access/EffectiveTree.vue'
import { useAction } from '../composables/useAction'
import { useAccessStore } from '../stores/access'

const { t } = useI18n()
const route = useRoute()
const store = useAccessStore()

const { busy, failure, run } = useAction()

const breadcrumb = computed(
  () => store.path.map((f) => (f.parent === null ? '' : f.name)).join('/') || '/'
)

const folderName = computed(() =>
  store.folder ? (store.folder.parent === null ? t('drive.everything') : store.folder.name) : ''
)

const allowed = computed(() => store.folder?.effect === 'allow')

/**
 * Names the folder whose rule decided the verdict of the open one.
 *
 * Walking up from the folder to the first written rule is what turns
 * "denied" into something the owner can act on: it says which rule to change.
 */
const decidedBy = computed(() => {
  const written = new Set(
    store.rules.filter((rule) => rule.document === null).map((rule) => rule.folder)
  )
  for (let i = store.path.length - 1; i >= 0; i -= 1) {
    const node = store.path[i]
    if (written.has(node.folder_id)) {
      return node.parent === null ? t('drive.everything') : node.name
    }
  }
  return null
})

const origin = computed(() => {
  if (!store.folder) {
    return ''
  }
  if (store.folder.source === 'own') {
    return allowed.value ? t('permissions.ownAllow') : t('permissions.ownDeny')
  }
  if (!decidedBy.value) {
    return t('permissions.noRuleAnywhere')
  }
  return allowed.value
    ? t('permissions.inheritedAllow', { from: decidedBy.value })
    : t('permissions.inheritedDeny', { from: decidedBy.value })
})

onMounted(() => {
  const wanted = typeof route.query.agent === 'string' ? route.query.agent : null
  const folder = typeof route.query.folder === 'string' ? route.query.folder : null
  void run(() => store.load(wanted, folder))
})
</script>

<template>
  <AppShell>
    <div class="page">
      <header class="banner">
        <div>
          <h2>{{ t('permissions.title') }}</h2>
          <p class="subtitle">{{ t('permissions.subtitle') }}</p>
        </div>
        <span v-if="store.agent" class="count">
          {{ t('permissions.reach', { name: store.agent.name, count: store.reachable }) }}
        </span>
      </header>

      <BaseAlert v-if="failure" tone="negative">{{ failure }}</BaseAlert>
      <BaseSpinner v-if="store.loading || busy" :label="t('common.loading')" />

      <p v-if="!store.agents.length && !store.loading" class="empty">
        {{ t('permissions.noAgents') }}
      </p>

      <div v-else class="columns">
        <aside class="pane">
          <span class="eyebrow">{{ t('permissions.pickAgent') }}</span>
          <button
            v-for="agent in store.agents"
            :key="agent.agent_id"
            type="button"
            :class="['pick', { on: agent.agent_id === store.agentId }]"
            @click="run(() => store.pick(agent.agent_id))"
          >
            {{ agent.name }}
          </button>

          <div class="rule" />

          <span class="eyebrow">{{ t('permissions.writtenRules') }}</span>
          <p v-if="!store.rules.length" class="none">{{ t('permissions.noRules') }}</p>
          <div v-for="written in store.rules" :key="written.permission_id" class="written">
            <span :class="['tag', written.effect]">{{ written.effect.toUpperCase() }}</span>
            <span class="target">
              {{
                store.folders.find((f) => f.folder_id === written.folder)?.name ??
                t('permissions.onDocument')
              }}
            </span>
          </div>
        </aside>

        <section class="pane">
          <div class="panehead">
            <span class="eyebrow">{{ t('permissions.resolvedTree') }}</span>
            <span class="eyebrow">{{ t('permissions.mostSpecific') }}</span>
          </div>
          <EffectiveTree
            :folders="store.folders"
            :selected="store.folderId"
            @open="(id) => (store.folderId = id)"
          />
        </section>

        <aside v-if="store.folder" class="pane">
          <span class="eyebrow">{{ t('permissions.folderCard') }}</span>
          <h3>{{ folderName }}</h3>
          <p class="path">{{ breadcrumb }}</p>

          <div :class="['verdict', allowed ? 'allow' : 'deny']">
            <strong>{{ allowed ? t('permissions.allowed') : t('permissions.denied') }}</strong>
            <span>{{ origin }}</span>
          </div>

          <div class="own">
            <span class="eyebrow">{{ t('permissions.ruleHere') }}</span>
            <span class="value">
              {{ store.ownRule ? store.ownRule.effect.toUpperCase() : t('permissions.none') }}
            </span>
          </div>

          <div class="buttons">
            <button
              type="button"
              class="grant"
              :disabled="busy"
              @click="run(() => store.setRule('allow'))"
            >
              {{ t('permissions.setAllow') }}
            </button>
            <button
              type="button"
              class="block"
              :disabled="busy"
              @click="run(() => store.setRule('deny'))"
            >
              {{ t('permissions.setDeny') }}
            </button>
          </div>
          <BaseButton v-if="store.ownRule" variant="quiet" @click="run(() => store.clearRule())">
            {{ t('permissions.clearRule') }}
          </BaseButton>
          <p class="hint">{{ t('permissions.clearHint') }}</p>
        </aside>
      </div>
    </div>
  </AppShell>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: var(--rm-space-4);
}

.banner {
  display: flex;
  align-items: flex-end;
  gap: var(--rm-space-4);
  flex-wrap: wrap;
  padding: var(--rm-space-4);
  background: var(--rm-accent);
  color: var(--rm-accent-ink);
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: var(--rm-radius);
  box-shadow: var(--rm-lift) var(--rm-lift) 0 var(--rm-shadow);
}

.banner div {
  margin-right: auto;
}

h2 {
  font-size: 26px;
}

.subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  opacity: 0.9;
  max-width: 62ch;
}

.count {
  padding: 6px 11px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 999px;
  background: var(--rm-lime);
  color: #17131f;
  font-family: var(--rm-font-mono);
  font-size: 11px;
  letter-spacing: 0.1em;
}

.columns {
  display: grid;
  grid-template-columns: minmax(0, 240px) minmax(0, 1fr) minmax(0, 340px);
  gap: var(--rm-space-4);
  align-items: start;
}

.pane {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
  padding: var(--rm-space-4);
  background: var(--rm-panel);
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: var(--rm-radius);
  box-shadow: var(--rm-lift) var(--rm-lift) 0 var(--rm-shadow);
}

.panehead {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.eyebrow {
  font-family: var(--rm-font-mono);
  font-size: 10.5px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--rm-muted);
}

.pick {
  padding: 11px;
  border: var(--rm-border-width) solid var(--rm-line);
  border-radius: 12px;
  background: var(--rm-panel2);
  color: var(--rm-ink);
  font-family: var(--rm-font-display);
  font-size: 15px;
  font-weight: 700;
  text-align: left;
  cursor: pointer;
}

.pick:hover {
  border-color: var(--rm-border);
}

.pick.on {
  border-color: var(--rm-border);
  background: var(--rm-pink);
  color: #17131f;
  box-shadow: 3px 3px 0 var(--rm-shadow);
}

.rule {
  height: var(--rm-border-width);
  background: var(--rm-line);
}

.written {
  display: flex;
  align-items: center;
  gap: var(--rm-space-2);
  font-size: 12.5px;
}

.tag {
  padding: 2px 7px;
  border-radius: 6px;
  font-family: var(--rm-font-mono);
  font-size: 10px;
  font-weight: 700;
}

.allow,
.tag.allow {
  background: var(--rm-pos-soft);
  color: var(--rm-pos);
}

.deny,
.tag.deny {
  background: var(--rm-neg-soft);
  color: var(--rm-neg);
}

.target {
  overflow-wrap: anywhere;
}

.none,
.empty {
  margin: 0;
  color: var(--rm-muted);
  font-size: 12.5px;
}

.empty {
  padding: var(--rm-space-4);
  border: var(--rm-border-width) dashed var(--rm-border);
  border-radius: 14px;
}

h3 {
  font-size: 20px;
  overflow-wrap: anywhere;
}

.path {
  margin: 0;
  font-family: var(--rm-font-mono);
  font-size: 11px;
  color: var(--rm-muted);
  overflow-wrap: anywhere;
}

.verdict {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 13px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 12px;
}

.verdict strong {
  font-family: var(--rm-font-display);
  font-size: 18px;
}

.verdict span {
  color: var(--rm-ink);
  font-size: 12.5px;
}

.own {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.value {
  font-family: var(--rm-font-mono);
  font-size: 12.5px;
  font-weight: 700;
}

.buttons {
  display: flex;
  gap: var(--rm-space-2);
  flex-wrap: wrap;
}

.grant,
.block {
  flex: 1;
  padding: 9px 12px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: var(--rm-radius-sm);
  font-weight: 700;
  cursor: pointer;
  box-shadow: 3px 3px 0 var(--rm-shadow);
}

.grant {
  background: var(--rm-lime);
  color: #17131f;
}

.block {
  background: var(--rm-neg-soft);
  color: var(--rm-neg);
}

.grant:disabled,
.block:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.hint {
  margin: 0;
  font-family: var(--rm-font-mono);
  font-size: 10.5px;
  color: var(--rm-muted);
}

@media (max-width: 1100px) {
  .columns {
    grid-template-columns: 1fr;
  }
}
</style>
