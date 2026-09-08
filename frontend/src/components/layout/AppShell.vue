<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import BaseButton from '../ui/BaseButton.vue'
import LanguageSwitcher from './LanguageSwitcher.vue'
import { useSessionStore } from '../../stores/session'

const { t } = useI18n()
const router = useRouter()
const session = useSessionStore()

/**
 * Closes the session and returns to the sign in screen.
 */
async function leave(): Promise<void> {
  await session.logOut()
  await router.push({ name: 'login' })
}
</script>

<template>
  <div class="shell">
    <header class="bar">
      <div class="brand">
        <strong>{{ t('app.name') }}</strong>
        <span class="tagline">{{ t('app.tagline') }}</span>
      </div>
      <nav class="links">
        <RouterLink :to="{ name: 'status' }">{{ t('nav.status') }}</RouterLink>
      </nav>
      <div class="tools">
        <LanguageSwitcher />
        <span v-if="session.owner" class="who">{{ session.owner.email }}</span>
        <BaseButton variant="quiet" @click="leave">{{ t('nav.signOut') }}</BaseButton>
      </div>
    </header>
    <main class="content">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  flex-direction: column;
  min-height: 100%;
}

.bar {
  display: flex;
  align-items: center;
  gap: var(--space-5);
  padding: var(--space-3) var(--space-5);
  background: var(--surface-raised);
  border-bottom: 1px solid var(--border);
}

.brand {
  display: flex;
  flex-direction: column;
}

.tagline {
  font-size: 0.82em;
  color: var(--text-muted);
}

.links {
  display: flex;
  gap: var(--space-4);
  margin-right: auto;
}

.links a {
  color: var(--text-muted);
  text-decoration: none;
  padding: var(--space-1) 0;
  border-bottom: 2px solid transparent;
}

.links a.router-link-active {
  color: var(--text);
  border-bottom-color: var(--accent);
}

.tools {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.who {
  color: var(--text-muted);
}

.content {
  flex: 1;
  padding: var(--space-5);
  max-width: 1100px;
  width: 100%;
  margin: 0 auto;
}

@media (max-width: 720px) {
  .bar {
    flex-wrap: wrap;
    gap: var(--space-3);
  }

  .tagline {
    display: none;
  }
}
</style>
