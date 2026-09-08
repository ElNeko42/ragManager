<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import BaseButton from '../ui/BaseButton.vue'
import LanguageSwitcher from './LanguageSwitcher.vue'
import ThemeToggle from './ThemeToggle.vue'
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
        <span class="mark" aria-hidden="true">rM</span>
        <span class="naming">
          <strong>{{ t('app.name') }}</strong>
          <span class="tagline">{{ t('app.tagline') }}</span>
        </span>
      </div>

      <nav class="links">
        <RouterLink :to="{ name: 'status' }">{{ t('nav.status') }}</RouterLink>
      </nav>

      <div class="tools">
        <LanguageSwitcher />
        <ThemeToggle />
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
  gap: var(--rm-space-4);
  min-height: 100%;
  padding: 18px 18px 40px;
  max-width: 1360px;
  margin: 0 auto;
  width: 100%;
}

.bar {
  display: flex;
  align-items: center;
  gap: var(--rm-space-4);
  flex-wrap: wrap;
  padding: 10px var(--rm-space-4);
  background: var(--rm-panel);
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: var(--rm-radius);
  box-shadow: var(--rm-lift) var(--rm-lift) 0 var(--rm-shadow);
}

.brand {
  display: flex;
  align-items: center;
  gap: var(--rm-space-3);
}

.mark {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 9px;
  background: var(--rm-accent);
  color: var(--rm-accent-ink);
  font-family: var(--rm-font-display);
  font-weight: 700;
  font-size: 16px;
}

.naming {
  display: flex;
  flex-direction: column;
  line-height: 1.15;
}

.naming strong {
  font-family: var(--rm-font-display);
  font-size: 17px;
}

.tagline {
  font-family: var(--rm-font-mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--rm-muted);
}

.links {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-right: auto;
}

.links a {
  padding: 7px 14px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 999px;
  background: var(--rm-panel2);
  color: var(--rm-ink);
  font-weight: 600;
  text-decoration: none;
}

.links a:hover {
  background: var(--rm-cyan);
  color: #17131f;
}

.links a.router-link-active {
  background: var(--rm-ink);
  color: var(--rm-panel);
  box-shadow: 3px 3px 0 var(--rm-shadow);
}

.tools {
  display: flex;
  align-items: center;
  gap: var(--rm-space-2);
  flex-wrap: wrap;
}

.who {
  font-family: var(--rm-font-mono);
  font-size: 11px;
  color: var(--rm-muted);
}

.content {
  flex: 1;
}

@media (max-width: 720px) {
  .tagline {
    display: none;
  }
}
</style>
