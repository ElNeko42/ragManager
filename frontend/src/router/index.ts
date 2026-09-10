import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

import { useSessionStore } from '../stores/session'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: { public: true }
  },
  {
    path: '/drive',
    name: 'drive',
    component: () => import('../views/DriveView.vue')
  },
  {
    path: '/agents',
    name: 'agents',
    component: () => import('../views/AgentsView.vue')
  },
  {
    path: '/permissions',
    name: 'permissions',
    component: () => import('../views/PermissionsView.vue')
  },
  {
    path: '/collections',
    name: 'collections',
    component: () => import('../views/CollectionsView.vue')
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('../views/SettingsView.vue')
  },
  {
    path: '/status',
    name: 'status',
    component: () => import('../views/StatusView.vue')
  },
  { path: '/', redirect: { name: 'drive' } },
  { path: '/:pathMatch(.*)*', redirect: { name: 'drive' } }
]

export const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  const session = useSessionStore()
  await session.ensureResolved()
  if (!to.meta.public && !session.owner) {
    return { name: 'login', query: { next: to.fullPath } }
  }
  if (to.meta.public && session.owner) {
    return { name: 'drive' }
  }
  return true
})
