import { apiClient } from './client'

export async function getUserHistory(userId) {
  const { data } = await apiClient.get(`/history/user/${userId}`)
  return data
}
