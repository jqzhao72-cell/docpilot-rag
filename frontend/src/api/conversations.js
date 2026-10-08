import { apiClient } from './client'
export async function createConversation(payload) {
  return (await apiClient.post('/conversations', payload)).data
}
export async function getUserConversations() {
  return (await apiClient.get('/conversations')).data
}
export async function getConversationMessages(id) {
  return (await apiClient.get(`/conversations/${id}/messages`)).data
}
export async function renameConversation(id, title) {
  return (await apiClient.patch(`/conversations/${id}`, { title })).data
}
export async function deleteConversation(id) {
  await apiClient.delete(`/conversations/${id}`)
}
