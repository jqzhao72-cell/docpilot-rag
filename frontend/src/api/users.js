import { apiClient } from './client'
export async function listUsers(offset = 0, limit = 100) {
  return (await apiClient.get('/users', { params: { offset, limit } })).data
}
export async function updateUserRole(userId, role) {
  return (await apiClient.put(`/users/${userId}/role`, { role })).data
}
