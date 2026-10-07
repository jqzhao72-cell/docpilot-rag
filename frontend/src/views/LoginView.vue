<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { register } from '../api/auth'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const mode = ref('login')
const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')
const notice = ref('')

async function submit() {
  error.value = ''
  notice.value = ''
  if (!username.value.trim() || !password.value) {
    error.value = '请输入用户名和密码。'
    return
  }
  loading.value = true
  try {
    if (mode.value === 'register') {
      const result = await register({ username: username.value.trim(), password: password.value })
      if (result.error) throw new Error(result.error)
      notice.value = '注册成功，请登录。'
      mode.value = 'login'
      password.value = ''
      return
    }
    await auth.login({ username: username.value.trim(), password: password.value })
    router.replace(route.query.redirect || '/chat')
  } catch (requestError) {
    error.value = requestError.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-hero">
      <div class="hero-grid"></div>
      <div class="hero-content">
        <span class="hero-kicker">ENTERPRISE RESEARCH INTELLIGENCE</span>
        <h1>让每一次回答，<br />都能回到可靠证据。</h1>
        <p>DocPilot 将企业文档、论文检索与可追溯引用整合在同一个知识工作台。</p>
        <div class="hero-points">
          <span>Hybrid Retrieval</span>
          <span>BGE Reranker</span>
          <span>Grounded Answer</span>
        </div>
      </div>
    </section>

    <section class="login-panel">
      <form class="login-card" @submit.prevent="submit">
        <div class="login-logo">D</div>
        <span class="eyebrow">WELCOME TO DOCPILOT</span>
        <h2>{{ mode === 'login' ? '登录知识工作台' : '创建员工账号' }}</h2>
        <p>{{ mode === 'login' ? '使用现有账号继续研究与问答。' : '新账号默认拥有 employee 权限。' }}</p>

        <label>
          用户名
          <input v-model="username" autocomplete="username" placeholder="请输入用户名" />
        </label>
        <label>
          密码
          <input
            v-model="password"
            autocomplete="current-password"
            type="password"
            placeholder="请输入密码"
          />
        </label>

        <p v-if="error" class="form-message error-message">{{ error }}</p>
        <p v-if="notice" class="form-message success-message">{{ notice }}</p>

        <button class="primary-button login-submit" :disabled="loading">
          {{ loading ? '处理中…' : mode === 'login' ? '登录' : '注册' }}
        </button>
        <button
          class="text-button"
          type="button"
          @click="mode = mode === 'login' ? 'register' : 'login'; error = ''; notice = ''"
        >
          {{ mode === 'login' ? '没有账号？创建一个' : '已有账号？返回登录' }}
        </button>
      </form>
    </section>
  </main>
</template>
