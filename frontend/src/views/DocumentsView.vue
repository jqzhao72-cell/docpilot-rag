<script setup>
import { computed, onMounted, ref } from 'vue'

import { deleteDocument, listDocuments } from '../api/documents'
import AppShell from '../components/AppShell.vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const documents = ref([])
const loading = ref(true)
const deleting = ref('')
const error = ref('')
const query = ref('')

const canDelete = computed(() => ['hr', 'admin'].includes(auth.user?.role))
const filteredDocuments = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  return keyword
    ? documents.value.filter((item) => item.filename.toLowerCase().includes(keyword))
    : documents.value
})

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    documents.value = await listDocuments(auth.user.user_id)
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
    await deleteDocument(document.filename, auth.user.user_id)
    await refresh()
  } catch (requestError) {
    error.value = requestError.message
  } finally {
    deleting.value = ''
  }
}

onMounted(refresh)
</script>

<template>
  <AppShell>
    <template #title>文档管理</template>
    <template #actions>
      <RouterLink class="primary-button compact-button" to="/knowledge-base">＋ 上传文档</RouterLink>
    </template>

    <section class="surface-card document-table-card">
      <div class="table-toolbar">
        <div>
          <span class="eyebrow">DOCUMENT CATALOG</span>
          <h2>可访问文档</h2>
        </div>
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
              <td><div class="file-cell"><span>PDF</span><strong>{{ document.filename }}</strong></div></td>
              <td>{{ document.chunks }}</td>
              <td><span class="role-pill">{{ document.role }}</span></td>
              <td><span class="indexed-status"><i></i> 已索引</span></td>
              <td class="action-cell">
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
  </AppShell>
</template>
