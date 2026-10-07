import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { login as loginRequest } from '../api/auth'

const STORAGE_KEY = 'docpilot_user'

function restoreUser() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY))
  } catch {
    localStorage.removeItem(STORAGE_KEY)
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref(restoreUser())
  const isAuthenticated = computed(() => Boolean(user.value?.user_id))

  async function login(credentials) {
    const data = await loginRequest(credentials)
    if (!data?.user_id) {
      throw new Error(data?.error || '用户名或密码错误')
    }
    user.value = data
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
    return data
  }

  function logout() {
    user.value = null
    localStorage.removeItem(STORAGE_KEY)
  }

  return { user, isAuthenticated, login, logout }
})
