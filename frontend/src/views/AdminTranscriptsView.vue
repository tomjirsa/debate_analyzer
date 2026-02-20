<template>
  <div>
    <h1>Transcript Registration Management</h1>
    <p>
      <router-link to="/admin">← Admin</router-link>
      | <router-link to="/admin/speakers">Manage speakers</router-link>
    </p>

    <div v-if="showLogin" class="login-box">
      <h2>Admin login</h2>
      <p>Enter the admin username and password configured on the server.</p>
      <label for="loginUser">Username</label>
      <input id="loginUser" v-model="loginUser" type="text" placeholder="username" autocomplete="username">
      <label for="loginPass">Password</label>
      <input id="loginPass" v-model="loginPass" type="password" placeholder="password" autocomplete="current-password">
      <br>
      <button type="button" @click="doLogin">Log in</button>
      <p class="err">{{ loginErr }}</p>
    </div>

    <template v-else>
      <section class="register-section">
        <h2>Register transcript</h2>
        <p>Enter S3 URI (e.g. <code>s3://bucket/jobs/xxx/transcripts/file.json</code>) or local path.</p>
        <label for="sourceUri">Source URI or path</label>
        <input id="sourceUri" v-model="sourceUri" type="text" placeholder="s3://... or path">
        <label for="title">Title (optional)</label>
        <input id="title" v-model="title" type="text" placeholder="Optional display title">
        <br>
        <button type="button" :disabled="registering" @click="register">Register</button>
        <p class="err">{{ registerErr }}</p>
      </section>

      <section>
        <h2>Transcripts</h2>
        <p class="err">{{ listErr }}</p>
        <table v-if="transcripts.length" class="transcript-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Source URI</th>
              <th>Speakers</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="t in transcripts" :key="t.id">
              <tr v-if="editingId !== t.id">
                <td>{{ t.title || '—' }}</td>
                <td class="uri-cell">{{ t.source_uri }}</td>
                <td>{{ t.speakers_count ?? '—' }}</td>
                <td>{{ formatDate(t.created_at) }}</td>
                <td>
                  <router-link :to="'/admin/annotate?transcript_id=' + encodeURIComponent(t.id)">Annotate</router-link>
                  <button type="button" @click="startEdit(t)">Edit</button>
                  <button type="button" @click="confirmDelete(t)">Delete</button>
                </td>
              </tr>
              <tr v-else class="edit-row">
                <td colspan="5">
                  <label>Title</label>
                  <input v-model="editTitle" type="text" placeholder="Title">
                  <label>Video path (optional)</label>
                  <input v-model="editVideoPath" type="text" placeholder="s3://... or path">
                  <button type="button" @click="saveEdit(t.id)">Save</button>
                  <button type="button" @click="cancelEdit">Cancel</button>
                  <span :class="editStatusClass">{{ editStatus }}</span>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
        <p v-else>No transcripts. Register one above.</p>
      </section>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAdminAuth } from '../composables/useAdminAuth'

const { setAuth, clearAuth, apiFetch } = useAdminAuth()

const showLogin = ref(false)
const loginUser = ref('')
const loginPass = ref('')
const loginErr = ref('')

const transcripts = ref([])
const listErr = ref('')
const sourceUri = ref('')
const title = ref('')
const registerErr = ref('')
const registering = ref(false)

const editingId = ref(null)
const editTitle = ref('')
const editVideoPath = ref('')
const editStatus = ref('')
const editStatusClass = computed(() => (editStatus.value === 'Saved.' ? 'ok' : editStatus.value ? 'err' : ''))

function formatDate(iso) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleDateString(undefined, { dateStyle: 'short' })
  } catch (_) {
    return iso
  }
}

function loadTranscripts() {
  listErr.value = ''
  apiFetch('/api/admin/transcripts')
    .then((r) => {
      if (r.status === 401) {
        clearAuth()
        showLogin.value = true
        return { _unauthorized: true }
      }
      return r.ok ? r.json() : Promise.reject(new Error(r.statusText))
    })
    .then((data) => {
      if (data && data._unauthorized) return
      showLogin.value = false
      transcripts.value = Array.isArray(data) ? data : []
      editingId.value = null
    })
    .catch((e) => { listErr.value = e.message })
}

function doLogin() {
  loginErr.value = ''
  const user = loginUser.value.trim()
  const pass = loginPass.value
  if (!user || !pass) {
    loginErr.value = 'Enter username and password.'
    return
  }
  setAuth(user, pass)
  apiFetch('/api/admin/transcripts')
    .then((r) => {
      if (r.status === 401) {
        clearAuth()
        loginErr.value = 'Invalid username or password.'
        return
      }
      if (!r.ok) throw new Error(r.statusText)
      return r.json()
    })
    .then((data) => {
      if (data && Array.isArray(data)) {
        showLogin.value = false
        transcripts.value = data
      }
    })
    .catch((e) => { loginErr.value = e.message })
}

function register() {
  registerErr.value = ''
  if (!sourceUri.value.trim()) {
    registerErr.value = 'Enter source URI or path.'
    return
  }
  registering.value = true
  apiFetch('/api/admin/transcripts/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_uri: sourceUri.value.trim(), title: title.value.trim() || null }),
  })
    .then((r) => (r.ok ? r.json() : r.json().then((j) => Promise.reject(new Error(j.detail || r.statusText)))))
    .then(() => {
      sourceUri.value = ''
      title.value = ''
      loadTranscripts()
    })
    .catch((e) => { registerErr.value = e.message || (e.detail || '') })
    .finally(() => { registering.value = false })
}

function startEdit(t) {
  editingId.value = t.id
  editTitle.value = t.title || ''
  editVideoPath.value = t.video_path || ''
  editStatus.value = ''
}

function cancelEdit() {
  editingId.value = null
  editStatus.value = ''
}

function saveEdit(id) {
  editStatus.value = ''
  apiFetch('/api/admin/transcripts/' + id, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: editTitle.value.trim() || null,
      video_path: editVideoPath.value.trim() || null,
    }),
  })
    .then((r) => (r.ok ? r.json() : r.json().then((j) => Promise.reject(new Error(j.detail || r.statusText)))))
    .then((updated) => {
      const idx = transcripts.value.findIndex((x) => x.id === id)
      if (idx >= 0) transcripts.value[idx] = updated
      editingId.value = null
      editStatus.value = 'Saved.'
    })
    .catch((e) => { editStatus.value = e.message || (e.detail || '') })
}

function confirmDelete(t) {
  const name = t.title || t.source_uri || t.id
  if (!confirm('Delete this transcript? Segments and speaker mappings will be removed.\n\n' + name)) return
  apiFetch('/api/admin/transcripts/' + t.id, { method: 'DELETE' })
    .then((r) => {
      if (r.status === 404) throw new Error('Transcript not found')
      if (r.status !== 204) throw new Error(r.statusText)
      loadTranscripts()
    })
    .catch((e) => { listErr.value = e.message })
}

onMounted(loadTranscripts)
</script>

<style scoped>
.login-box {
  background: #f0f8ff;
  padding: 1rem;
  border-radius: 6px;
  margin-bottom: 1.5rem;
  max-width: 320px;
}
.login-box input { width: 100%; }
.register-section { margin-bottom: 2rem; }
.register-section input[type="text"] { max-width: 480px; width: 100%; }
.transcript-table { width: 100%; }
.uri-cell { max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.edit-row td { background: #f9f9f9; padding: 0.75rem; }
.edit-row label { display: inline-block; margin-right: 0.5rem; }
.edit-row input { margin-right: 0.5rem; max-width: 300px; }
</style>
