import { apiClient } from './client'

export async function login(credentials) {
  const { data } = await apiClient.post('/login', credentials)
  return data
}

export async function register(credentials) {
  const { data } = await apiClient.post('/register', credentials)
  return data
}
