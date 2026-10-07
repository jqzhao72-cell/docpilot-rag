import { apiClient } from './client'

export async function askQuestion(payload) {
  const { data } = await apiClient.post('/chat', payload)
  return data
}
