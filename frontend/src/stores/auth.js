import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { TOKEN_KEY } from '../api/client'
import { login as loginRequest, logout as logoutRequest, getCurrentUser } from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const isAuthenticated = computed(() => Boolean(user.value && sessionStorage.getItem(TOKEN_KEY)))
  let initializing
  localStorage.removeItem('docpilot_user')

  function clear() {
    user.value = null
    sessionStorage.removeItem(TOKEN_KEY)
  }
  window.addEventListener('docpilot-session-expired', clear)

  async function initialize() {
    if (!sessionStorage.getItem(TOKEN_KEY)) return clear()
    if (!initializing) {
      initializing = getCurrentUser().then((data) => { user.value = data })
        .finally(() => { initializing = null })
    }
    try { await initializing } catch (error) {
      if (error.status === 401 || error.status === 403) clear()
      else throw error
    }
  }

  async function login(credentials) {
    const data = await loginRequest(credentials)
    sessionStorage.setItem(TOKEN_KEY, data.access_token)
    user.value = { user_id: data.user_id, username: data.username, role: data.role }
    return user.value
  }
  async function logout() {
    try { await logoutRequest() } finally { clear() }
  }
  return { user, isAuthenticated, initialize, login, logout }
})
