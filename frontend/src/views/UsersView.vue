<script setup>
import { onMounted, ref } from 'vue'
import AppShell from '../components/AppShell.vue'
import { listUsers, updateUserRole } from '../api/users'
import { useAuthStore } from '../stores/auth'
const auth = useAuthStore()
const users = ref([])
const total = ref(0)
const offset = ref(0)
const loading = ref(false)
const error = ref('')
const notice = ref('')
async function refresh() {
  loading.value = true
  error.value = ''
  try { const result = await listUsers(offset.value); users.value = result.items; total.value = result.total }
  catch (e) { error.value = e.message } finally { loading.value = false }
}
async function changeRole(user, event) {
  const role = event.target.value
  event.target.value = user.role
  if (!window.confirm(`将 ${user.username} 的角色修改为 ${role}？该用户需要重新登录。`)) return
  loading.value = true
  try { await updateUserRole(user.user_id, role); notice.value = '角色已更新，该用户旧会话凭证已失效。'; await refresh() }
  catch (e) { error.value = e.message } finally { loading.value = false }
}
async function page(delta) { offset.value += delta; await refresh() }
onMounted(refresh)
</script>

<template>
  <AppShell>
    <template #title>用户管理</template>
    <section class="surface-card document-table-card">
      <div class="table-toolbar"><h2>用户与角色</h2><span>共 {{ total }} 位用户</span></div>
      <p v-if="error" class="form-message error-message">{{ error }}</p>
      <p v-if="notice" class="form-message success-message">{{ notice }}</p>
      <div class="table-scroll"><table class="document-table">
        <thead><tr><th>ID</th><th>用户名</th><th>角色</th></tr></thead>
        <tbody><tr v-for="user in users" :key="user.user_id">
          <td>{{ user.user_id }}</td><td>{{ user.username }}</td>
          <td><select :value="user.role" :disabled="loading || user.user_id === auth.user?.user_id" @change="changeRole(user, $event)">
            <option>employee</option><option>hr</option><option>admin</option>
          </select></td>
        </tr></tbody>
      </table></div>
      <button class="text-button" :disabled="loading || offset === 0" @click="page(-100)">上一页</button>
      <button class="text-button" :disabled="loading || offset + 100 >= total" @click="page(100)">下一页</button>
    </section>
  </AppShell>
</template>
