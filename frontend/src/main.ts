import { createPinia } from 'pinia'
import { createApp } from 'vue'

import '@fontsource/chakra-petch/500.css'
import '@fontsource/chakra-petch/700.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/700.css'
import '@fontsource/space-grotesk/400.css'
import '@fontsource/space-grotesk/500.css'
import '@fontsource/space-grotesk/700.css'

import App from './App.vue'
import { handleUnauthorized } from './api/client'
import { i18n, persistLocale, resolveInitialLocale } from './i18n'
import { router } from './router'
import { useSessionStore } from './stores/session'
import { useThemeStore } from './stores/theme'
import './styles/tokens.css'
import './styles/base.css'

persistLocale(resolveInitialLocale())

const app = createApp(App)
app.use(createPinia())
useThemeStore().apply()

handleUnauthorized(() => {
  useSessionStore().forget()
  const here = router.currentRoute.value
  if (here.name !== 'login') {
    void router.push({ name: 'login', query: { next: here.fullPath } })
  }
})

app.use(i18n).use(router).mount('#app')
