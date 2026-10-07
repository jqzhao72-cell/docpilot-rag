import { apiClient } from './client'

export async function listDocuments(userId) {
  const { data } = await apiClient.get('/documents', {
    params: { user_id: userId },
  })
  return data
}

export async function uploadDocument({ file, role, userId }) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('role', role)
  formData.append('user_id', userId)
  const { data } = await apiClient.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function deleteDocument(filename, userId) {
  const { data } = await apiClient.delete(`/documents/${encodeURIComponent(filename)}`, {
    params: { user_id: userId },
  })
  return data
}
