<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import BaseAlert from '../components/ui/BaseAlert.vue'
import BaseButton from '../components/ui/BaseButton.vue'
import BaseField from '../components/ui/BaseField.vue'
import BaseInput from '../components/ui/BaseInput.vue'
import BaseWindow from '../components/ui/BaseWindow.vue'
import LanguageSwitcher from '../components/layout/LanguageSwitcher.vue'
import ThemeToggle from '../components/layout/ThemeToggle.vue'
import { ApiError } from '../api/client'
import { describeError } from '../api/errors'
import { useSessionStore } from '../stores/session'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const session = useSessionStore()

const email = ref('')
const password = ref('')
const submitting = ref(false)
const error = ref('')

/**
 * Signs in and continues to wherever the visitor was heading.
 *
 * Turns the failure into one of the few messages the panel knows how to say,
 * so a rejected password, a rate limit and an unreachable server do not all
 * look the same to whoever is trying to get in.
 */
async function submit(): Promise<void> {
  submitting.value = true
  error.value = ''
  try {
    await session.logIn(email.value, password.value)
    const next = typeof route.query.next === 'string' ? route.query.next : '/'
    await router.push(next)
  } catch (cause) {
    error.value = describe(cause)
  } finally {
    submitting.value = false
  }
}

/**
 * Chooses the message that matches why signing in failed.
 */
function describe(cause: unknown): string {
  if (cause instanceof ApiError) {
    if (cause.status === 401) {
      return t('login.invalid')
    }
    if (cause.status === 429) {
      return t('login.throttled')
    }
  }
  return describeError(cause, t)
}
</script>

<template>
  <div class="page">
    <div class="corner">
      <LanguageSwitcher />
      <ThemeToggle />
    </div>

    <BaseWindow title="RAGMANAGER.EXE" class="panel">
      <form class="form" @submit.prevent="submit">
        <div>
          <h1>{{ t('login.title') }}</h1>
          <p class="subtitle">{{ t('login.subtitle') }}</p>
        </div>

        <BaseField :label="t('login.email')" for-id="email">
          <BaseInput
            id="email"
            v-model="email"
            type="email"
            autocomplete="username"
            required
            :disabled="submitting"
          />
        </BaseField>

        <BaseField :label="t('login.password')" for-id="password">
          <BaseInput
            id="password"
            v-model="password"
            type="password"
            autocomplete="current-password"
            required
            :disabled="submitting"
          />
        </BaseField>

        <BaseAlert v-if="error" tone="negative">{{ error }}</BaseAlert>

        <BaseButton type="submit" variant="primary" block :disabled="submitting">
          {{ submitting ? t('login.submitting') : t('login.submit') }}
        </BaseButton>

        <p class="hint">{{ t('login.hint') }}</p>
      </form>
    </BaseWindow>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100%;
  /*
   * The top and bottom gutters both clear the fixed language and theme
   * controls, so the window stays centred while it can no longer slide under
   * them on a short or narrow screen.
   */
  padding: calc(var(--rm-space-5) * 2 + 20px) var(--rm-space-5);
}

.corner {
  position: fixed;
  top: var(--rm-space-4);
  right: var(--rm-space-4);
  display: flex;
  align-items: center;
  gap: var(--rm-space-2);
}

.panel {
  width: 100%;
  max-width: 420px;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

h1 {
  font-size: 30px;
}

.subtitle {
  margin: 6px 0 0;
  color: var(--rm-muted);
}

.hint {
  margin: 0;
  font-family: var(--rm-font-mono);
  font-size: 11px;
  color: var(--rm-muted);
}
</style>
