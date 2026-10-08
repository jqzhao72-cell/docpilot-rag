<script setup>
import { computed, onMounted, ref } from 'vue'

import { listDocuments, uploadDocument } from '../api/documents'
import AppShell from '../components/AppShell.vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const documents = ref([])
const selectedFile = ref(null)
const documentRole = ref('employee')
const loading = ref(false)
const loadingDocuments = ref(true)
const error = ref('')
const notice = ref('')

const canManage = computed(() => ['hr', 'admin'].includes(auth.user?.role))
const roleOptions = computed(() =>
  auth.user?.role === 'admin' ? ['employee', 'hr', 'admin'] : ['employee', 'hr'],
)
const chunkCount = computed(() => documents.value.reduce((sum, item) => sum + item.chunks, 0))
const scopeCount = computed(() => new Set(documents.value.map((item) => item.role)).size)

async function refresh() {
  loadingDocuments.value = true
  try {
    documents.value = await listDocuments('company')
  } catch (requestError) {
    error.value = requestError.message
  } finally {
    loadingDocuments.value = false
  }
}

function chooseFile(event) {
  selectedFile.value = event.target.files?.[0] || null
}

async function upload() {
  if (!selectedFile.value) {
    error.value = '请先选择 PDF、DOCX 或 TXT 文件。'
    return
  }
  loading.value = true
  error.value = ''
  notice.value = ''
  try {
    const result = await uploadDocument({
      file: selectedFile.value,
      role: documentRole.value,
    })
    notice.value = `${result.filename} 已完成解析并写入 ${result.chunks} 个 chunks。`
    selectedFile.value = null
    await refresh()
  } catch (requestError) {
    error.value = requestError.message
  } finally {
    loading.value = false
  }
}

onMounted(refresh)
</script>

<template>
  <AppShell>
    <template #title>知识库</template>
    <template #actions><span class="soft-chip">Chroma · Persistent</span></template>

    <div class="page-stack">
      <section class="metric-grid">
        <article class="metric-card">
          <span>可访问文档</span><strong>{{ documents.length }}</strong><small>按当前角色过滤</small>
        </article>
        <article class="metric-card">
          <span>知识片段</span><strong>{{ chunkCount }}</strong><small>Company collection</small>
        </article>
        <article class="metric-card">
          <span>权限层级</span><strong>{{ scopeCount }}</strong><small>当前可见范围</small>
        </article>
      </section>

      <section class="content-grid two-columns">
        <article class="surface-card knowledge-intro">
          <span class="eyebrow">KNOWLEDGE OPERATIONS</span>
          <h2>把可信文档转化为可检索知识</h2>
          <p>上传后的文档会经过解析、结构化切分、Embedding，并写入带权限元数据的 Chroma collection。</p>
          <ol class="process-list">
            <li><span>01</span><div><strong>文档解析</strong><p>支持 PDF、DOCX、TXT。</p></div></li>
            <li><span>02</span><div><strong>结构化切分</strong><p>保留章节与 chunk 元信息。</p></div></li>
            <li><span>03</span><div><strong>向量入库</strong><p>根据角色控制文档可见范围。</p></div></li>
          </ol>
        </article>

        <article class="surface-card upload-card">
          <div class="card-heading">
            <div><span class="eyebrow">INGESTION</span><h2>上传新文档</h2></div>
          </div>
          <template v-if="canManage">
            <label class="drop-zone">
              <input type="file" accept=".pdf,.docx,.txt" @change="chooseFile" />
              <span class="upload-icon">⇧</span>
            <strong>{{ selectedFile?.name || '选择文档' }}</strong>
            <small>PDF / DOCX / TXT · 最大 25 MB · 同名文档不会覆盖</small>
            </label>
            <label class="field-label">
              文档权限
              <select v-model="documentRole">
                <option v-for="role in roleOptions" :key="role" :value="role">{{ role }}</option>
              </select>
            </label>
            <button class="primary-button full-button" :disabled="loading" @click="upload">
              {{ loading ? '正在解析与入库…' : '上传并构建索引' }}
            </button>
          </template>
          <div v-else class="permission-note">
            当前账号为 employee，仅可使用已有知识库。上传功能需要 HR 或 Admin 权限。
          </div>
          <p v-if="error" class="form-message error-message">{{ error }}</p>
          <p v-if="notice" class="form-message success-message">{{ notice }}</p>
        </article>
      </section>

      <section class="surface-card">
        <div class="card-heading">
          <div><span class="eyebrow">RECENT DOCUMENTS</span><h2>最近可见文档</h2></div>
          <RouterLink class="text-link" to="/documents">查看全部 →</RouterLink>
        </div>
        <div v-if="loadingDocuments" class="muted-state">加载知识库统计…</div>
        <div v-else class="document-preview-grid">
          <article v-for="document in documents.slice(0, 6)" :key="document.filename">
            <span class="file-icon">PDF</span>
            <div><strong>{{ document.filename }}</strong><small>{{ document.chunks }} chunks</small></div>
            <span class="role-pill">{{ document.role }}</span>
          </article>
        </div>
      </section>
    </div>
  </AppShell>
</template>
