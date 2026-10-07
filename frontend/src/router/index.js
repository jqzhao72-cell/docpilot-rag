import { createRouter, createWebHistory } from 'vue-router'

import { pinia } from '../stores'
import { useAuthStore } from '../stores/auth'
import ChatView from '../views/ChatView.vue'
import DocumentsView from '../views/DocumentsView.vue'
import HistoryView from '../views/HistoryView.vue'
import KnowledgeBaseView from '../views/KnowledgeBaseView.vue'
import LoginView from '../views/LoginView.vue'

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
    { path: '/:pathMatch(.*)*', redirect: '/chat' },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore(pinia)
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guestOnly && auth.isAuthenticated) {
    return { name: 'chat' }
  }
  return true
})

export default router
