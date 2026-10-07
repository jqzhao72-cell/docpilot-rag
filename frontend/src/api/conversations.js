import { apiClient } from './client'

export async function createConversation(payload) {
  const { data } = await apiClient.post('/conversations', payload)
  return data
}

export async function getUserConversations(userId) {
  const { data } = await apiClient.get(`/conversations/user/${userId}`)
  return data
}

export async function getConversationMessages(conversationId) {
  const { data } = await apiClient.get(`/conversations/${conversationId}/messages`)
  return data
}
