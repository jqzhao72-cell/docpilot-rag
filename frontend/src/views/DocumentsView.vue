<script setup>
import { computed, onMounted, ref } from 'vue'

import { deleteDocument, listDocuments, viewDocument, downloadDocument, setDocumentRole } from '../api/documents'
import AppShell from '../components/AppShell.vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const documents = ref([])
const loading = ref(true)
const deleting = ref('')
const error = ref('')
const query = ref('')
const knowledgeBase = ref('company')
const preview = ref(null)

const canDelete = computed(() => ['hr', 'admin'].includes(auth.user?.role))
const filteredDocuments = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  return keyword
    ? documents.value.filter((item) => item.filename.toLowerCase().includes(keyword))
    : documents.value
})

async function refresh() {
  preview.value = null
  loading.value = true
  error.value = ''
  try {
    documents.value = await listDocuments(knowledgeBase.value)
  } catch (requestError) {
    error.value = requestError.message
  } finally {
    loading.value = false
  }
}

async function removeDocument(document) {
  if (!window.confirm(`确认删除 ${document.filename}？该操作会同步删除向量数据。`)) return
  deleting.value = document.filename
  error.value = ''
  try {
    await deleteDocument(document.filename, knowledgeBase.value)
    await refresh()
  } catch (requestError) {
    error.value = requestError.message
  } finally {
    deleting.value = ''
  }
}

onMounted(refresh)

async function view(document) {
  error.value = ''
  try { preview.value = await viewDocument(document.filename, knowledgeBase.value) }
  catch (e) { error.value = e.message }
}
async function download(document) {
  error.value = ''
  try { await downloadDocument(document.filename, knowledgeBase.value) }
  catch (e) { error.value = e.message }
}
async function changeRole(document, event) {
  const role = event.target.value
  event.target.value = document.role
  if (!window.confirm(`将 ${document.filename} 的可见范围改为 ${role}？`)) return
  try { await setDocumentRole(document.filename, role, knowledgeBase.value); await refresh() }
  catch (e) { error.value = e.message }
}
</script>

<template>
  <AppShell>
    <template #title>文档管理</template>
    <template #actions>
      <RouterLink v-if="canDelete" class="primary-button compact-button" to="/knowledge-base">＋ 上传文档</RouterLink>
    </template>

    <section class="surface-card document-table-card">
      <div class="table-toolbar">
        <div>
          <span class="eyebrow">DOCUMENT CATALOG</span>
          <h2>可访问文档</h2>
        </div>
        <select v-model="knowledgeBase" @change="refresh"><option value="company">企业知识库</option><option value="paper">论文知识库</option></select>
        <input v-model="query" class="search-input" placeholder="搜索文件名…" />
      </div>

      <p v-if="error" class="form-message error-message">{{ error }}</p>
      <div v-if="loading" class="muted-state large-state">正在加载文档…</div>
      <div v-else-if="!filteredDocuments.length" class="muted-state large-state">没有匹配的文档。</div>
      <div v-else class="table-scroll">
        <table class="document-table">
          <thead><tr><th>文档</th><th>Chunks</th><th>权限</th><th>状态</th><th></th></tr></thead>
          <tbody>
            <tr v-for="document in filteredDocuments" :key="document.filename">
              <td><div class="file-cell"><span>{{ document.filename.split('.').pop()?.toUpperCase() }}</span><strong>{{ document.filename }}</strong></div></td>
              <td>{{ document.chunks }}</td>
              <td><select v-if="auth.user?.role === 'admin'" :value="document.role" @change="changeRole(document, $event)"><option>employee</option><option>hr</option><option>admin</option></select><span v-else class="role-pill">{{ document.role }}</span></td>
              <td><span class="indexed-status"><i></i> 已索引</span></td>
              <td class="action-cell">
                <button class="text-button" @click="view(document)">查看正文</button>
                <button v-if="knowledgeBase === 'company'" class="text-button" @click="download(document)">下载</button>
                <button
                  v-if="canDelete"
                  class="danger-text-button"
                  :disabled="deleting === document.filename"
                  @click="removeDocument(document)"
                >
                  {{ deleting === document.filename ? '删除中…' : '删除' }}
                </button>
                <span v-else>—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
    <section v-if="preview" class="surface-card document-preview">
      <div class="table-toolbar"><h2>{{ preview.filename }}</h2><button class="text-button" @click="preview = null">关闭</button></div>
      <article v-for="(chunk, index) in preview.chunks" :key="index"><small>{{ chunk.section || `片段 ${index + 1}` }}</small><p>{{ chunk.text }}</p></article>
    </section>
  </AppShell>
</template>
