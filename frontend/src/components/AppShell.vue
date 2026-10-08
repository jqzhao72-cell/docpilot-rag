<script setup>
import { useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const navigation = [
  { to: '/chat', label: '智能问答', icon: '✦' },
  { to: '/knowledge-base', label: '知识库', icon: '◇' },
  { to: '/documents', label: '文档管理', icon: '▤' },
  { to: '/history', label: '问答历史', icon: '◷' },
]

async function logout() {
  try { await auth.logout() } finally { router.push('/login') }
}
</script>

<template>
  <div class="app-shell">
    <aside class="global-sidebar">
      <div class="brand-block">
        <div class="brand-mark">D</div>
        <div>
          <strong>DocPilot</strong>
          <span>Knowledge Workspace</span>
        </div>
      </div>

      <nav class="global-nav" aria-label="主导航">
        <RouterLink v-if="auth.user?.role === 'admin'" to="/users"><span>♙</span>用户管理</RouterLink>
        <RouterLink v-for="item in navigation" :key="item.to" :to="item.to">
          <span class="nav-icon">{{ item.icon }}</span>
          {{ item.label }}
        </RouterLink>
      </nav>

      <div class="sidebar-user">
        <div class="user-avatar">{{ auth.user?.username?.slice(0, 1)?.toUpperCase() }}</div>
        <div class="user-meta">
          <strong>{{ auth.user?.username }}</strong>
          <span>{{ auth.user?.role }}</span>
        </div>
        <button class="icon-button" title="退出登录" @click="logout">↪</button>
      </div>
    </aside>

    <main class="shell-main">
      <header class="topbar">
        <div>
          <span class="eyebrow">DOCPILOT / WORKSPACE</span>
          <h1><slot name="title">DocPilot</slot></h1>
        </div>
        <slot name="actions" />
      </header>
      <div class="shell-content">
        <slot />
      </div>
    </main>
  </div>
</template>
