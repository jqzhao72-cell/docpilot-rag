import { apiClient } from './client'
const documentUrl = (filename) => `/documents/${encodeURIComponent(filename)}`
export async function listDocuments(knowledgeBase = 'company') {
  return (await apiClient.get('/documents', { params: { knowledge_base: knowledgeBase } })).data
}
export async function uploadDocument({ file, role }) {
  const form = new FormData()
  form.append('file', file)
  form.append('role', role)
  form.append('knowledge_base', 'company')
  return (await apiClient.post('/documents', form)).data
}
export async function deleteDocument(filename, knowledgeBase = 'company') {
  await apiClient.delete(documentUrl(filename), { params: { knowledge_base: knowledgeBase } })
}
export async function viewDocument(filename, knowledgeBase = 'company') {
  return (await apiClient.get(documentUrl(filename) + '/content', { params: { knowledge_base: knowledgeBase } })).data
}
export async function downloadDocument(filename, knowledgeBase = 'company') {
  const { data } = await apiClient.get(documentUrl(filename) + '/download', {
    params: { knowledge_base: knowledgeBase }, responseType: 'blob',
  })
  const url = URL.createObjectURL(data)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
export async function setDocumentRole(filename, role, knowledgeBase) {
  return (await apiClient.put(documentUrl(filename) + '/role', { role },
    { params: { knowledge_base: knowledgeBase } })).data
}
