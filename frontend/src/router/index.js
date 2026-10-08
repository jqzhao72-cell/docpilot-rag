import { createRouter, createWebHistory } from 'vue-router'

import { pinia } from '../stores'
import { useAuthStore } from '../stores/auth'
import ChatView from '../views/ChatView.vue'
import DocumentsView from '../views/DocumentsView.vue'
import HistoryView from '../views/HistoryView.vue'
import KnowledgeBaseView from '../views/KnowledgeBaseView.vue'
import LoginView from '../views/LoginView.vue'
import UsersView from '../views/UsersView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { guestOnly: true } },
    { path: '/', redirect: '/chat' },
    { path: '/chat', name: 'chat', component: ChatView, meta: { requiresAuth: true } },
    {
      path: '/knowledge-base',
      name: 'knowledge-base',
      component: KnowledgeBaseView,
      meta: { requiresAuth: true },
    },
    {
      path: '/documents',
      name: 'documents',
      component: DocumentsView,
      meta: { requiresAuth: true },
    },
    { path: '/history', name: 'history', component: HistoryView, meta: { requiresAuth: true } },
    { path: '/users', name: 'users', component: UsersView, meta: { requiresAuth: true, roles: ['admin'] } },
    { path: '/:pathMatch(.*)*', redirect: '/chat' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore(pinia)
  await auth.initialize()
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guestOnly && auth.isAuthenticated) {
    return { name: 'chat' }
  }
  if (to.meta.roles && !to.meta.roles.includes(auth.user?.role)) return { name: 'chat' }
  return true
})

window.addEventListener('docpilot-session-expired', () => {
  if (router.currentRoute.value.name !== 'login') router.replace('/login')
})

export default router
