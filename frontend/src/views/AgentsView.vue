<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import AppShell from '../components/layout/AppShell.vue'
import BaseAlert from '../components/ui/BaseAlert.vue'
import BaseButton from '../components/ui/BaseButton.vue'
import BaseField from '../components/ui/BaseField.vue'
import BaseIcon from '../components/ui/BaseIcon.vue'
import BaseInput from '../components/ui/BaseInput.vue'
import BaseModal from '../components/ui/BaseModal.vue'
import BaseSpinner from '../components/ui/BaseSpinner.vue'
import UnsavedGuard from '../components/ui/UnsavedGuard.vue'
import AgentCard from '../components/agents/AgentCard.vue'
import McpConnection from '../components/agents/McpConnection.vue'
import TokenReveal from '../components/agents/TokenReveal.vue'
import { useAction } from '../composables/useAction'
import { readConnectionUrl } from '../api/agents'
import { useAgentsStore } from '../stores/agents'

const { t } = useI18n()
const router = useRouter()
const agents = useAgentsStore()

const creating = ref(false)
const name = ref('')
const expiry = ref('')
const { busy, failure, run, clear } = useAction()

const reveal = ref<{ token: string; agentName: string } | null>(null)
const connecting = ref<string | null>(null)
const mcpUrl = ref('')

const dirty = computed(
  () => creating.value && Boolean(name.value.trim() || expiry.value)
)

/**
 * Leaves the create dialog, dropping whatever it was complaining about.
 */
function closeCreate(): void {
  creating.value = false
  clear()
}

/**
 * Turns the date the owner typed into what the API expects, or nothing.
 *
 * The date is read as the owner's own end of day and sent as the instant that
 * matches it, so a token bought on a calendar day dies when that day does
 * wherever the owner is.
 */
function expiresAt(): string | null {
  return expiry.value ? new Date(`${expiry.value}T23:59:59`).toISOString() : null
}

/**
 * Registers the agent and puts its token in front of the owner.
 */
function submit(): void {
  const wanted = name.value.trim()
  if (!wanted) {
    return
  }
  void run(async () => {
    const created = await agents.create(wanted, expiresAt())
    creating.value = false
    name.value = ''
    expiry.value = ''
    reveal.value = { token: created.token, agentName: created.agent.name }
  })
}

/**
 * Mints an extra token for an agent that already exists.
 */
function issue(agentId: string, agentName: string): void {
  void run(async () => {
    const issued = await agents.issue(agentId, null)
    reveal.value = { token: issued.token, agentName }
  })
}

/**
 * Reads the agents and the address their clients connect to.
 *
 * A failure to read the address is not worth stopping the page for: the rest
 * of it works, and the connection blocks are simply not offered.
 */
onMounted(() =>
  void run(async () => {
    await agents.load()
    try {
      mcpUrl.value = (await readConnectionUrl()).url
    } catch {
      mcpUrl.value = ''
    }
  })
)
</script>

<template>
  <AppShell>
    <UnsavedGuard :dirty="dirty" />
    <div class="page">
      <header class="head">
        <div>
          <h2>{{ t('agents.title') }}</h2>
          <p class="subtitle">{{ t('agents.subtitle') }}</p>
        </div>
        <BaseButton variant="primary" @click="creating = true">
          <BaseIcon name="plus" :size="18" />
          {{ t('agents.newAgent') }}
        </BaseButton>
      </header>

      <BaseAlert v-if="failure && !creating" tone="negative">{{ failure }}</BaseAlert>
      <BaseSpinner v-if="agents.loading || busy" :label="t('common.loading')" />

      <p v-if="!agents.rows.length && !agents.loading" class="empty">{{ t('agents.none') }}</p>

      <div v-else class="grid">
        <AgentCard
          v-for="row in agents.rows"
          :key="row.agent.agent_id"
          :row="row"
          @issue="issue(row.agent.agent_id, row.agent.name)"
          @revoke="(tokenId) => run(() => agents.revoke(row.agent.agent_id, tokenId))"
          @remove="run(() => agents.remove(row.agent.agent_id))"
          @simulate="router.push({ name: 'permissions', query: { agent: row.agent.agent_id } })"
          @connect="connecting = row.agent.name"
        />
      </div>
    </div>

    <BaseModal v-if="creating" :title="t('agents.newAgentTitle')" @close="closeCreate">
      <form class="form" @submit.prevent="submit">
        <BaseAlert v-if="failure" tone="negative">{{ failure }}</BaseAlert>
        <BaseField :label="t('agents.name')" for-id="agent-name">
          <BaseInput id="agent-name" v-model="name" required :disabled="busy" />
        </BaseField>
        <BaseField
          :label="t('agents.expiry')"
          for-id="agent-expiry"
          :hint="t('agents.expiryHint')"
        >
          <BaseInput id="agent-expiry" v-model="expiry" type="date" :disabled="busy" />
        </BaseField>
        <div class="buttons">
          <BaseButton variant="quiet" :disabled="busy" @click="closeCreate">
            {{ t('drive.cancel') }}
          </BaseButton>
          <BaseButton type="submit" variant="primary" :disabled="busy">
            {{ t('agents.createGo') }}
          </BaseButton>
        </div>
      </form>
    </BaseModal>

    <BaseModal
      v-if="reveal"
      :title="t('agents.tokenTitle')"
      :dismissible="false"
      @close="reveal = null"
    >
      <TokenReveal
        :token="reveal.token"
        :agent-name="reveal.agentName"
        :mcp-url="mcpUrl"
        @done="reveal = null"
      />
    </BaseModal>

    <BaseModal
      v-if="connecting"
      :title="t('agents.connectTitle')"
      @close="connecting = null"
    >
      <div class="connect">
        <McpConnection v-if="mcpUrl" :url="mcpUrl" :name="connecting" />
        <BaseAlert v-else tone="negative">{{ t('agents.connectUnavailable') }}</BaseAlert>

        <div class="buttons">
          <BaseButton @click="connecting = null">{{ t('common.close') }}</BaseButton>
        </div>
      </div>
    </BaseModal>
  </AppShell>
</template>

<style scoped>
.connect {
  display: flex;
  flex-direction: column;
  gap: var(--rm-space-3);
}

.buttons {
  display: flex;
  justify-content: flex-end;
  gap: var(--rm-space-2);
  padding-top: var(--rm-space-2);
  border-top: var(--rm-border-width) dotted var(--rm-line);
}

.page {
  display: flex;
  flex-direction: column;
  gap: var(--rm-space-4);
}

.head {
  display: flex;
  align-items: flex-end;
  gap: var(--rm-space-3);
  flex-wrap: wrap;
}

.head div {
  margin-right: auto;
}

h2 {
  font-size: 26px;
}

.subtitle {
  margin: 3px 0 0;
  color: var(--rm-muted);
  font-size: 13px;
  max-width: 70ch;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 320px), 1fr));
  gap: var(--rm-space-4);
}

.empty {
  margin: 0;
  padding: var(--rm-space-4);
  border: var(--rm-border-width) dashed var(--rm-border);
  border-radius: 14px;
  color: var(--rm-muted);
}

.form {
  display: flex;
  flex-direction: column;
  gap: var(--rm-space-4);
}
</style>
