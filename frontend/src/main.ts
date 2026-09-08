import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { i18n, persistLocale, resolveInitialLocale } from './i18n'
import { router } from './router'
import './styles/tokens.css'
import './styles/base.css'

persistLocale(resolveInitialLocale())

createApp(App).use(createPinia()).use(i18n).use(router).mount('#app')
