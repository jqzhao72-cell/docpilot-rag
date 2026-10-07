<script setup>
import { computed, onMounted, ref } from 'vue'

import { getUserHistory } from '../api/history'
import AppShell from '../components/AppShell.vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const records = ref([])
const loading = ref(true)
const error = ref('')
const query = ref('')
const expanded = ref(null)

const filteredRecords = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  if (!keyword) return records.value
  return records.value.filter(
    (item) =>
      item.question.toLowerCase().includes(keyword) || item.answer.toLowerCase().includes(keyword),
  )
})

function sourceCount(value) {
  if (!value) return 0
  try {
    return Array.isArray(value) ? value.length : JSON.parse(value).length
  } catch {
    return 0
  }
}

onMounted(async () => {
  try {
    records.value = await getUserHistory(auth.user.user_id)
  } catch (requestError) {
    error.value = requestError.message
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <AppShell>
    <template #title>问答历史</template>

    <section class="surface-card history-card">
      <div class="table-toolbar">
        <div><span class="eyebrow">RESEARCH LOG</span><h2>历史问答记录</h2></div>
        <input v-model="query" class="search-input" placeholder="搜索问题或答案…" />
      </div>
      <p v-if="error" class="form-message error-message">{{ error }}</p>
      <div v-if="loading" class="muted-state large-state">正在加载历史…</div>
      <div v-else-if="!filteredRecords.length" class="muted-state large-state">暂无问答记录。</div>
      <div v-else class="history-list">
        <article v-for="record in filteredRecords" :key="record.id" class="history-item">
          <button class="history-summary" @click="expanded = expanded === record.id ? null : record.id">
            <span class="history-index">{{ String(record.id).padStart(2, '0') }}</span>
            <div>
              <strong>{{ record.question }}</strong>
              <p>{{ record.answer }}</p>
            </div>
            <div class="history-meta">
              <span>{{ sourceCount(record.sources) }} sources</span>
              <small>{{ record.created_time?.slice(0, 16) }}</small>
            </div>
          </button>
          <div v-if="expanded === record.id" class="history-detail">
            <span class="eyebrow">FULL ANSWER</span>
            <p>{{ record.answer }}</p>
          </div>
        </article>
      </div>
    </section>
  </AppShell>
</template>
