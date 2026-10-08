<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'

import { askQuestion } from '../api/chat'
import {
  createConversation,
  getConversationMessages,
  getUserConversations,
  renameConversation,
  deleteConversation,
} from '../api/conversations'
import AppShell from '../components/AppShell.vue'
import SourcePanel from '../components/SourcePanel.vue'
const conversations = ref([])
const activeConversationId = ref(null)
const messages = ref([])
const question = ref('')
const activeSources = ref([])
const timings = ref(null)
const loading = ref(false)
const loadingConversations = ref(true)
const loadingMessages = ref(false)
const error = ref('')
const messageList = ref(null)
const knowledgeBase = ref('company')
let selectionVersion = 0

const activeConversation = computed(() =>
  conversations.value.find((item) => item.id === activeConversationId.value),
)

function parseSources(value) {
  if (Array.isArray(value)) return value
  if (!value) return []
  try {
    return JSON.parse(value)
  } catch {
    return []
  }
}

async function refreshConversations() {
  conversations.value = await getUserConversations()
}

async function selectConversation(id) {
  if (loading.value) return
  const version = ++selectionVersion
  loadingMessages.value = true
  try {
    activeConversationId.value = id
    error.value = ''
    timings.value = null
    const result = await getConversationMessages(id)
    if (version !== selectionVersion) return
    knowledgeBase.value = activeConversation.value?.knowledge_base || 'company'
    messages.value = result.map((message) => ({ ...message, sources: parseSources(message.sources) }))
    const lastAssistant = [...messages.value].reverse().find((message) => message.role === 'assistant')
    activeSources.value = lastAssistant?.sources || []
    await scrollToBottom()
  } catch (requestError) { if (version === selectionVersion) error.value = requestError.message }
  finally { if (version === selectionVersion) loadingMessages.value = false }
}

function newConversation() {
  if (loading.value) return
  selectionVersion++
  loadingMessages.value = false
  activeConversationId.value = null
  messages.value = []
  activeSources.value = []
  timings.value = null
  error.value = ''
}

async function ensureConversation(prompt) {
  if (activeConversationId.value) return activeConversationId.value
  const created = await createConversation({
    knowledge_base: knowledgeBase.value,
    title: prompt.slice(0, 42),
  })
  if (created.error) throw new Error(created.error)
  activeConversationId.value = created.id
  await refreshConversations()
  return created.id
}

async function scrollToBottom() {
  await nextTick()
  if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight
}

async function sendQuestion() {
  const prompt = question.value.trim()
  if (!prompt || loading.value || loadingMessages.value) return
  question.value = ''
  error.value = ''
  loading.value = true
  activeSources.value = []
  timings.value = null

  try {
    const conversationId = await ensureConversation(prompt)
    messages.value.push({ role: 'user', content: prompt, sources: [] })
    await scrollToBottom()

    const result = await askQuestion({
      question: prompt,
      conversation_id: conversationId,
    })
    const sources = result.sources || []
    messages.value.push({ role: 'assistant', content: result.answer, sources })
    activeSources.value = sources
    timings.value = result.timings || null
    await refreshConversations()
    await scrollToBottom()
  } catch (requestError) {
    error.value = requestError.message
    question.value = prompt
    if (activeConversationId.value) {
      try { messages.value = await getConversationMessages(activeConversationId.value) } catch { /* retain request error */ }
    }
  } finally {
    loading.value = false
  }
}

function showMessageSources(message) {
  if (message.role === 'assistant') activeSources.value = message.sources || []
}

async function renameActive() {
  const title = window.prompt('会话标题', activeConversation.value?.title)
  if (!title?.trim()) return
  try { await renameConversation(activeConversationId.value, title.trim()); await refreshConversations() }
  catch (requestError) { error.value = requestError.message }
}
async function deleteActive() {
  if (!window.confirm('删除此会话及其历史记录？')) return
  try { await deleteConversation(activeConversationId.value); newConversation(); await refreshConversations() }
  catch (requestError) { error.value = requestError.message }
}

onMounted(async () => {
  try {
    await refreshConversations()
    if (conversations.value.length) await selectConversation(conversations.value[0].id)
  } catch (requestError) {
    error.value = requestError.message
  } finally {
    loadingConversations.value = false
  }
})
</script>

<template>
  <AppShell>
    <template #title>智能问答</template>
    <template #actions>
      <select v-model="knowledgeBase" :disabled="loading || Boolean(activeConversationId)">
        <option value="company">企业知识库</option><option value="paper">论文知识库</option>
      </select>
    </template>

    <div class="chat-workspace">
      <aside class="conversation-panel">
        <button class="primary-button new-chat-button" :disabled="loading" @click="newConversation">＋ 新建会话</button>
        <div class="conversation-heading">
          <span>最近会话</span>
          <span>{{ conversations.length }}</span>
        </div>
        <div v-if="loadingConversations" class="muted-state">正在加载会话…</div>
        <div v-else-if="!conversations.length" class="muted-state">还没有会话，从一个问题开始。</div>
        <button
          v-for="conversation in conversations"
          :key="conversation.id"
          class="conversation-item"
          :disabled="loading"
          :class="{ active: conversation.id === activeConversationId }"
          @click="selectConversation(conversation.id)"
        >
          <span>{{ conversation.title }}</span>
          <small>{{ conversation.updated_time?.slice(0, 16) }}</small>
        </button>
      </aside>

      <section class="chat-main-panel">
        <div class="chat-context-bar">
          <div>
            <span class="eyebrow">CONVERSATION</span>
            <h2>{{ activeConversation?.title || '新会话' }}</h2>
            <div v-if="activeConversationId">
              <button class="text-button" :disabled="loading" @click="renameActive">重命名</button>
              <button class="danger-text-button" :disabled="loading" @click="deleteActive">删除会话</button>
            </div>
          </div>
          <div v-if="timings" class="timing-summary">
            总耗时 {{ (timings.total_ms / 1000).toFixed(1) }}s
          </div>
        </div>

        <div ref="messageList" class="message-list">
          <div v-if="!messages.length" class="chat-welcome">
            <div class="welcome-symbol">✦</div>
            <span class="eyebrow">RESEARCH WITH EVIDENCE</span>
            <h2>今天想从{{ knowledgeBase === 'company' ? '企业文档' : '论文' }}中了解什么？</h2>
            <p>DocPilot 会执行混合检索、精排与证据约束生成，并为答案保留可追溯来源。</p>
            <div v-if="knowledgeBase === 'paper'" class="suggestion-grid">
              <button @click="question = 'triple-negative breast cancer treatment'">TNBC 治疗进展</button>
              <button @click="question = 'AKR1C3 and chemotherapy resistance'">AKR1C3 与耐药</button>
              <button @click="question = 'tumor immune microenvironment'">肿瘤免疫微环境</button>
            </div>
          </div>

          <article
            v-for="(message, index) in messages"
            :key="message.id || index"
            class="message-row"
            :class="message.role"
            @click="showMessageSources(message)"
          >
            <div class="message-avatar">{{ message.role === 'user' ? '你' : 'D' }}</div>
            <div class="message-body">
              <div class="message-role">{{ message.role === 'user' ? 'You' : 'DocPilot' }}</div>
              <p>{{ message.content }}</p>
              <button v-if="message.sources?.length" class="source-link">
                查看 {{ message.sources.length }} 条来源证据 →
              </button>
            </div>
          </article>

          <article v-if="loading" class="message-row assistant">
            <div class="message-avatar">D</div>
            <div class="message-body">
              <div class="message-role">DocPilot</div>
              <div class="thinking"><span></span><span></span><span></span> 正在检索并组织答案</div>
            </div>
          </article>
        </div>

        <div class="composer-wrap">
          <p v-if="error" class="form-message error-message">{{ error }}</p>
          <form class="composer" @submit.prevent="sendQuestion">
            <textarea
              v-model="question"
              rows="2"
              placeholder="向 DocPilot 提问，Enter 换行，点击发送提交…"
              :disabled="loading"
            ></textarea>
            <button class="send-button" :disabled="loading || loadingMessages || !question.trim()">发送 ↑</button>
          </form>
          <span class="composer-note">答案由检索证据生成，请结合来源原文判断。</span>
        </div>
      </section>

      <SourcePanel :sources="activeSources" :loading="loading" />
    </div>
  </AppShell>
</template>
