// Test the same API selector imported by ChatView, using the actual Vite modules.
import assert from 'node:assert/strict'
import { createServer } from 'vite'

globalThis.sessionStorage = { getItem: () => 'test-bearer' }
const server = await createServer({ server: { middlewareMode: true } })
try {
  const { requestForMode } = await server.ssrLoadModule('/src/api/chatMode.js')
  const { apiClient } = await server.ssrLoadModule('/src/api/client.js')
  const seen = []
  apiClient.defaults.adapter = async (config) => {
    seen.push({ url: config.url, auth: config.headers.Authorization, data: JSON.parse(config.data) })
    return { data: { answer: 'test', sources: [], tool_trace: [] }, status: 200, headers: {}, config }
  }
  const payload = { question: 'GENIE3', conversation_id: 1 }
  await requestForMode('rag')(payload)
  await requestForMode('agent')(payload)
  assert.deepEqual(seen.map(x => x.url), ['/chat', '/agent/chat'])
  assert.ok(seen.every(x => x.auth === 'Bearer test-bearer'))
  assert.deepEqual(seen.map(x => x.data), [payload, payload])
  const view = await server.ssrLoadModule('/src/views/ChatView.vue')
  assert.ok(view.default)
  console.log('PASS: ChatView compiles; both mode endpoints, payloads and Bearer token checked.')
} finally {
  await server.close()
}
