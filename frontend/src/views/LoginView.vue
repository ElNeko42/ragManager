<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import BaseAlert from '../components/ui/BaseAlert.vue'
import BaseButton from '../components/ui/BaseButton.vue'
import BaseCard from '../components/ui/BaseCard.vue'
import BaseField from '../components/ui/BaseField.vue'
import BaseInput from '../components/ui/BaseInput.vue'
import LanguageSwitcher from '../components/layout/LanguageSwitcher.vue'
import { ApiError } from '../api/client'
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
    return t('common.unexpectedError')
  }
  return t('login.unreachable')
}
</script>

<template>
  <div class="page">
    <div class="corner">
      <LanguageSwitcher />
    </div>
    <BaseCard :title="t('login.title')" :subtitle="t('login.subtitle')" class="panel">
      <form class="form" @submit.prevent="submit">
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
      </form>
    </BaseCard>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100%;
  padding: var(--space-5);
}

.corner {
  position: fixed;
  top: var(--space-4);
  right: var(--space-4);
}

.panel {
  width: 100%;
  max-width: 380px;
}

.form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
</style>
