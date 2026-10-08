import axios from 'axios'
export const TOKEN_KEY = 'docpilot_token'
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
  timeout: 180000,
})
apiClient.interceptors.request.use((config) => {
  const token = sessionStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401 && error.config?.url !== '/login') {
      sessionStorage.removeItem(TOKEN_KEY)
      window.dispatchEvent(new Event('docpilot-session-expired'))
    }
    let body = error.response?.data
    if (body instanceof Blob) {
      try { body = JSON.parse(await body.text()) } catch { body = null }
    }
    const detail = body?.detail
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg).join('；')
      : detail || body?.error || error.message || '请求失败'
    const result = new Error(message)
    result.status = error.response?.status
    return Promise.reject(result)
  },
)
