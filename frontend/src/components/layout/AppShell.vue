<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import BaseButton from '../ui/BaseButton.vue'
import BaseIcon from '../ui/BaseIcon.vue'
import LanguageSwitcher from './LanguageSwitcher.vue'
import ThemeToggle from './ThemeToggle.vue'
import { useTooTight } from '../../composables/useTooTight'
import { useSessionStore } from '../../stores/session'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const session = useSessionStore()

const open = ref(false)
const bar = ref<HTMLElement | null>(null)

/**
 * Whether the bar still has room for the words next to the marks.
 *
 * Below that width the destinations travel as marks alone rather than as a
 * second row: a header that wraps puts the tools underneath the brand, which
 * is neither where they belong nor where anyone looks for them.
 */
const { tight, measure } = useTooTight(bar)

watch(locale, () => void nextTick(measure))

const destinations = [
  { name: 'drive', icon: 'folder', label: 'nav.drive' },
  { name: 'agents', icon: 'robot', label: 'nav.agents' },
  { name: 'permissions', icon: 'shield', label: 'nav.permissions' },
  { name: 'collections', icon: 'layers', label: 'nav.collections' },
  { name: 'status', icon: 'pulse', label: 'nav.status' },
  { name: 'settings', icon: 'gear', label: 'nav.settings' }
]

/**
 * Closes the small screen menu once it has taken the visitor somewhere.
 *
 * A menu left open would cover the page it just opened, which on a phone is
 * the whole page.
 */
watch(() => route.fullPath, () => {
  open.value = false
})

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
    <header ref="bar" :class="['bar', { tight }]">
      <div class="brand">
        <span class="mark" aria-hidden="true">rM</span>
        <span class="naming">
          <strong>{{ t('app.name') }}</strong>
          <span class="tagline">{{ t('app.tagline') }}</span>
        </span>

        <button
          type="button"
          class="menu"
          :aria-expanded="open"
          aria-controls="app-nav"
          :aria-label="t('common.menu')"
          @click="open = !open"
        >
          <BaseIcon :name="open ? 'close' : 'menu'" :size="20" />
        </button>
      </div>

      <nav id="app-nav" :class="['links', { open }]">
        <RouterLink
          v-for="place in destinations"
          :key="place.name"
          :to="{ name: place.name }"
          :title="t(place.label)"
        >
          <BaseIcon :name="place.icon" :size="18" />
          <span>{{ t(place.label) }}</span>
        </RouterLink>
      </nav>

      <div :class="['tools', { open }]">
        <LanguageSwitcher />
        <ThemeToggle />
        <BaseButton
          variant="quiet"
          class="signout"
          :title="t('nav.signOut')"
          :aria-label="t('nav.signOut')"
          @click="leave"
        >
          <BaseIcon name="logout" :size="16" />
          <span class="label">{{ t('nav.signOut') }}</span>
        </BaseButton>
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
  gap: var(--rm-space-3);
  flex-wrap: nowrap;
  overflow: hidden;
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
  flex: none;
}

.mark {
  display: grid;
  place-items: center;
  flex: none;
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
  white-space: nowrap;
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

/* The menu button only exists where the bar can no longer hold everything. */
.menu {
  display: none;
  place-items: center;
  width: 38px;
  height: 38px;
  margin-left: auto;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 10px;
  background: var(--rm-panel2);
  color: var(--rm-ink);
  cursor: pointer;
}

.menu:hover {
  background: var(--rm-cyan);
  color: var(--rm-ink-on-bright);
}

.links {
  display: flex;
  gap: 5px;
  flex: none;
  flex-wrap: nowrap;
  margin-right: auto;
}

.links a {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  flex: none;
  padding: 7px 12px;
  border: var(--rm-border-width) solid var(--rm-border);
  border-radius: 999px;
  background: var(--rm-panel2);
  color: var(--rm-ink);
  font-weight: 600;
  text-decoration: none;
  white-space: nowrap;
}

.links a:hover {
  background: var(--rm-cyan);
  color: var(--rm-ink-on-bright);
}

.links a.router-link-active {
  background: var(--rm-ink);
  color: var(--rm-panel);
  box-shadow: 3px 3px 0 var(--rm-shadow);
}

.tools {
  display: flex;
  align-items: center;
  gap: 7px;
  flex: none;
  flex-wrap: nowrap;
  margin-left: auto;
}

/*
 * Signing out is one press among the destinations, not one of them, so it
 * keeps the mark and gives up the word to the six that need one. The word
 * stays in the page for anyone who cannot see the mark, and comes back in the
 * menu on a small screen, where there is room for it.
 */
.signout .label {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  white-space: nowrap;
  clip-path: inset(50%);
}

.content {
  flex: 1;
}

/*
 * The word stays in the page rather than being removed: a link a screen reader
 * announces as nothing is a link nobody can follow, and the tooltip covers the
 * pointer.
 */
.tight .links a span {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  white-space: nowrap;
  clip-path: inset(50%);
}

.tight .links a {
  padding: 9px 11px;
}

/*
 * Below the width where six destinations and the tools still fit on one line,
 * the bar becomes a brand with a button, and everything else drops into a
 * column underneath it rather than wrapping into an unreadable pile.
 */
@media (max-width: 860px) {
  .shell {
    padding: 12px 12px 32px;
  }

  .bar {
    flex-direction: column;
    align-items: stretch;
    gap: var(--rm-space-3);
    overflow: visible;
  }

  .menu {
    display: grid;
  }

  .links,
  .tools {
    display: none;
  }

  .links.open,
  .tools.open {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    margin: 0;
    padding-top: var(--rm-space-3);
    border-top: var(--rm-border-width) dotted var(--rm-line);
  }

  .tools.open {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
  }

  .links a {
    justify-content: flex-start;
    padding: 11px 14px;
    border-radius: var(--rm-radius-sm);
  }

  .links a span,
  .tight .links a span,
  .tools.open .signout .label {
    position: static;
    width: auto;
    height: auto;
    margin: 0;
    overflow: visible;
    clip-path: none;
  }

  .tight .links a {
    padding: 11px 14px;
  }
}

@media (max-width: 480px) {
  .tagline {
    display: none;
  }
}
</style>
