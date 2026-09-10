<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import AppShell from '../components/layout/AppShell.vue'
import BaseAlert from '../components/ui/BaseAlert.vue'
import BaseButton from '../components/ui/BaseButton.vue'
import BaseCard from '../components/ui/BaseCard.vue'
import BaseField from '../components/ui/BaseField.vue'
import BaseIcon from '../components/ui/BaseIcon.vue'
import BaseInput from '../components/ui/BaseInput.vue'
import UnsavedGuard from '../components/ui/UnsavedGuard.vue'
import { ApiError } from '../api/client'
import { describeError } from '../api/errors'
import { SUPPORTED_LOCALES, persistLocale } from '../i18n'
import type { Locale } from '../i18n'
import { useSessionStore } from '../stores/session'
import { useThemeStore } from '../stores/theme'
import type { ThemeChoice } from '../stores/theme'

const { t, locale } = useI18n()
const session = useSessionStore()
const themes = useThemeStore()

const busy = ref(false)
const failure = ref('')
const email = ref('')
const password = ref('')
const repeat = ref('')
const current = ref('')
const done = ref('')

const themeChoices: { value: ThemeChoice; icon: string; label: string }[] = [
  { value: 'light', icon: 'sun', label: 'settings.themeLight' },
  { value: 'dark', icon: 'moon', label: 'settings.themeDark' },
  { value: 'system', icon: 'monitor', label: 'settings.themeSystem' }
]

const languages: Record<Locale, string> = { en: 'English', es: 'Español' }

const dirty = computed(() =>
  Boolean(email.value.trim() || password.value || repeat.value || current.value)
)

const wanted = computed(() => ({
  email: email.value.trim().toLowerCase(),
  password: password.value
}))

const nothingToDo = computed(() => !wanted.value.email && !wanted.value.password)

/**
 * Follows the desktop, or fixes the panel on one of the two themes.
 */
function chooseTheme(choice: ThemeChoice): void {
  themes.choose(choice)
}

/**
 * Switches the panel's language and remembers it on this device.
 */
function chooseLanguage(code: Locale): void {
  locale.value = code
  persistLocale(code)
}

/**
 * Sends whatever the owner filled in, leaving the rest of the account alone.
 *
 * The two halves travel together because the server takes them together, and
 * because a form that saved the address while silently dropping a mistyped
 * password would be worse than one that refuses both.
 */
async function submit(): Promise<void> {
  done.value = ''
  failure.value = ''
  if (nothingToDo.value) {
    return
  }
  if (wanted.value.email && wanted.value.email === session.owner?.email) {
    failure.value = t('settings.sameEmail')
    return
  }
  if (wanted.value.password && wanted.value.password !== repeat.value) {
    failure.value = t('settings.mismatch')
    return
  }
  const changing = { ...wanted.value }
  busy.value = true
  try {
    await session.changeAccount({
      current_password: current.value,
      ...(changing.email ? { email: changing.email } : {}),
      ...(changing.password ? { new_password: changing.password } : {})
    })
    email.value = ''
    password.value = ''
    repeat.value = ''
    current.value = ''
    done.value = changing.password ? t('settings.passwordChanged') : t('settings.emailChanged')
  } catch (cause) {
    failure.value = describe(cause)
  } finally {
    busy.value = false
  }
}

/**
 * Chooses the message that matches why the change was refused.
 *
 * A wrong current password is answered on that field, and is worth saying in
 * the panel's own words: it is the one rejection here that is simply a typo.
 */
function describe(cause: unknown): string {
  if (cause instanceof ApiError && cause.status === 400) {
    const body = cause.body
    if (body && typeof body === 'object' && 'current_password' in body) {
      return t('settings.wrongPassword')
    }
  }
  return describeError(cause, t)
}

/**
 * Drops the outcome of the last attempt as soon as the form is touched again.
 */
function touched(): void {
  done.value = ''
  failure.value = ''
}
</script>

<template>
  <AppShell>
    <UnsavedGuard :dirty="dirty" />
    <div class="page">
      <header class="head">
        <div>
          <h2>{{ t('settings.title') }}</h2>
          <p class="subtitle">{{ t('settings.subtitle') }}</p>
        </div>
      </header>

      <div class="cards">
        <BaseCard :title="t('settings.appearance')" :subtitle="t('settings.appearanceHint')">
          <div class="group">
            <span class="eyebrow">{{ t('settings.theme') }}</span>
            <div class="choices" role="radiogroup" :aria-label="t('settings.theme')">
              <button
                v-for="option in themeChoices"
                :key="option.value"
                type="button"
                role="radio"
                :aria-checked="themes.choice === option.value"
                :class="['choice', { on: themes.choice === option.value }]"
                @click="chooseTheme(option.value)"
              >
                <BaseIcon :name="option.icon" :size="20" />
                {{ t(option.label) }}
              </button>
            </div>
            <p v-if="themes.choice === 'system'" class="hint">
              {{
                t('settings.themeSystemHint', {
                  theme: (themes.theme === 'dark'
                    ? t('settings.themeDark')
                    : t('settings.themeLight')
                  ).toLowerCase()
                })
              }}
            </p>
          </div>

          <div class="group">
            <span class="eyebrow">{{ t('settings.language') }}</span>
            <div class="choices" role="radiogroup" :aria-label="t('settings.language')">
              <button
                v-for="code in SUPPORTED_LOCALES"
                :key="code"
                type="button"
                role="radio"
                :aria-checked="locale === code"
                :class="['choice', { on: locale === code }]"
                @click="chooseLanguage(code)"
              >
                <span class="code">{{ code.toUpperCase() }}</span>
                {{ languages[code] }}
              </button>
            </div>
            <p class="hint">{{ t('settings.languageHint') }}</p>
          </div>
        </BaseCard>

        <BaseCard :title="t('settings.account')" :subtitle="t('settings.accountHint')">
          <p class="who">
            <BaseIcon name="mail" :size="18" />
            <span class="eyebrow">{{ t('settings.signedInAs') }}</span>
            <strong>{{ session.owner?.email }}</strong>
          </p>

          <form class="form" @submit.prevent="submit">
            <BaseAlert v-if="failure" tone="negative">{{ failure }}</BaseAlert>
            <BaseAlert v-else-if="done" tone="positive">{{ done }}</BaseAlert>

            <BaseField :label="t('settings.newEmail')" for-id="new-email">
              <BaseInput
                id="new-email"
                v-model="email"
                type="email"
                autocomplete="username"
                :disabled="busy"
                @input="touched"
              />
            </BaseField>

            <div class="pair">
              <BaseField :label="t('settings.newPassword')" for-id="new-password">
                <BaseInput
                  id="new-password"
                  v-model="password"
                  type="password"
                  autocomplete="new-password"
                  :disabled="busy"
                  @input="touched"
                />
              </BaseField>

              <BaseField :label="t('settings.repeatPassword')" for-id="repeat-password">
                <BaseInput
                  id="repeat-password"
                  v-model="repeat"
                  type="password"
                  autocomplete="new-password"
                  :disabled="busy"
                  @input="touched"
                />
              </BaseField>
            </div>

            <div class="rule" />

            <BaseField
              :label="t('settings.currentPassword')"
              for-id="current-password"
              :hint="t('settings.currentPasswordHint')"
            >
              <BaseInput
                id="current-password"
                v-model="current"
                type="password"
                autocomplete="current-password"
                required
                :disabled="busy"
                @input="touched"
              />
            </BaseField>

            <div class="buttons">
              <BaseButton
                type="submit"
                variant="primary"
                :disabled="busy || nothingToDo || !current"
              >
                <BaseIcon name="key" :size="18" />
                {{ busy ? t('settings.saving') : t('common.save') }}
              </BaseButton>
            </div>
          </form>
        </BaseCard>
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

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 340px), 1fr));
  gap: var(--rm-space-4);
  align-items: start;
}

.group {
  display: flex;
  flex-direction: column;
  gap: var(--rm-space-2);
}

.eyebrow {
  font-family: var(--rm-font-mono);
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--rm-muted);
}

.choices {
  display: flex;
  gap: var(--rm-space-2);
  flex-wrap: wrap;
}

.choice {
  display: inline-flex;
  align-items: center;
  gap: var(--rm-space-2);
  flex: 1 1 auto;
  justify-content: center;
  padding: 10px var(--rm-space-3);
  border: var(--rm-border-width) solid var(--rm-line);
  border-radius: var(--rm-radius-sm);
  background: var(--rm-panel2);
  color: var(--rm-ink);
  font-weight: 600;
  cursor: pointer;
  transition: transform 90ms ease, box-shadow 90ms ease, background 90ms ease;
}

.choice:hover:not(.on) {
  border-color: var(--rm-border);
}

.choice.on {
  border-color: var(--rm-border);
  background: var(--rm-cyan);
  color: var(--rm-ink-on-bright);
  box-shadow: 3px 3px 0 var(--rm-shadow);
}

.code {
  font-family: var(--rm-font-mono);
  font-size: 11px;
  letter-spacing: 0.1em;
  opacity: 0.7;
}

.hint {
  margin: 0;
  font-family: var(--rm-font-mono);
  font-size: 11px;
  color: var(--rm-muted);
}

.who {
  display: flex;
  align-items: center;
  gap: var(--rm-space-2);
  flex-wrap: wrap;
  margin: 0;
  padding: var(--rm-space-3);
  border: var(--rm-border-width) solid var(--rm-line);
  border-radius: 12px;
  background: var(--rm-panel2);
  overflow-wrap: anywhere;
}

.form {
  display: flex;
  flex-direction: column;
  gap: var(--rm-space-4);
}

.pair {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 180px), 1fr));
  gap: var(--rm-space-3);
}

.rule {
  height: var(--rm-border-width);
  background: var(--rm-line);
}

.buttons {
  display: flex;
  justify-content: flex-end;
}
</style>
