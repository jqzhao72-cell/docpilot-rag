<script setup>
defineProps({
  sources: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})

function pageLabel(source) {
  if (source.page) return source.page
  if (source.page_start == null && source.page_end == null) return '未知'
  if (source.page_end == null || source.page_start === source.page_end) return source.page_start
  return `${source.page_start}-${source.page_end}`
}
</script>

<template>
  <aside class="source-panel">
    <div class="panel-heading">
      <div>
        <span class="eyebrow">EVIDENCE</span>
        <h2>来源证据</h2>
      </div>
      <span class="count-badge">{{ sources.length }}</span>
    </div>

    <div v-if="loading" class="source-empty">正在整理证据…</div>
    <div v-else-if="!sources.length" class="source-empty">
      提问后，这里会展示用于生成答案的文档片段。
    </div>
    <div v-else class="source-list">
      <article v-for="source in sources" :key="`${source.index}-${source.id}`" class="source-card">
        <div class="source-card-head">
          <span class="citation-badge">[{{ source.index }}]</span>
          <span class="type-badge">{{ source.chunk_type || 'text' }}</span>
        </div>
        <strong>{{ source.source || '未知来源' }}</strong>
        <dl class="source-meta">
          <div><dt>页码</dt><dd>{{ pageLabel(source) }}</dd></div>
          <div><dt>章节</dt><dd>{{ source.section || '未标注' }}</dd></div>
        </dl>
        <p>{{ source.text || '该来源未返回正文预览。' }}</p>
      </article>
    </div>
  </aside>
</template>
