import { apiClient } from './client'
export async function getUserHistory() {
  return (await apiClient.get('/history')).data
}
export async function getAllHistory(userId) {
  return (await apiClient.get('/admin/history', { params: { user_id: userId } })).data
}
