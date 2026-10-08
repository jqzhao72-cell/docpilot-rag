import { apiClient } from './client'

export async function login(credentials) {
  const { data } = await apiClient.post('/login', credentials)
  return data
}

export async function register(credentials) {
  const { data } = await apiClient.post('/register', credentials)
  return data
}

export async function getCurrentUser() {
  return (await apiClient.get('/users/me')).data
}

export async function logout() {
  await apiClient.post('/logout')
}
