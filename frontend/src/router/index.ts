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
    path: '/status',
    name: 'status',
    component: () => import('../views/StatusView.vue')
  },
  { path: '/', redirect: { name: 'status' } },
  { path: '/:pathMatch(.*)*', redirect: { name: 'status' } }
]

export const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  const session = useSessionStore()
  await session.ensureResolved()
  if (!to.meta.public && !session.owner) {
    return { name: 'login', query: { next: to.fullPath } }
  }
  if (to.meta.public && session.owner) {
    return { name: 'status' }
  }
  return true
})
