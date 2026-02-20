<template>
  <div>
    <p><router-link to="/admin">← Admin</router-link></p>
    <h1>Manage speakers</h1>
    <p class="err">{{ err }}</p>

    <div v-if="showLogin" class="login-box">
      <h2>Admin login</h2>
      <p>Log in to manage speakers. You can also <router-link to="/admin">log in on the Admin page</router-link> first.</p>
      <label for="loginUser">Username</label>
      <input id="loginUser" v-model="loginUser" type="text" placeholder="username" autocomplete="username">
      <label for="loginPass">Password</label>
      <input id="loginPass" v-model="loginPass" type="password" placeholder="password" autocomplete="current-password">
      <br>
      <button type="button" @click="doLogin">Log in</button>
      <p class="err">{{ loginErr }}</p>
    </div>

    <div v-else>
      <div id="addForm" class="add-form">
        <h2>Add speaker</h2>
        <label>First name</label>
        <input v-model="newFirstName" type="text" placeholder="First name">
        <label>Surname</label>
        <input v-model="newSurname" type="text" placeholder="Surname">
        <label>Slug (optional)</label>
        <input v-model="newSlug" type="text" placeholder="url-slug">
        <label>Short description (optional)</label>
        <textarea v-model="newShortDescription" placeholder="Short description" rows="3"></textarea>
        <label>Bio (optional)</label>
        <textarea v-model="newBio" placeholder="Bio" rows="3"></textarea>
        <br>
        <button type="button" @click="addSpeaker">Add speaker</button>
        <span :class="addStatusClass">{{ addStatus }}</span>
      </div>

      <h2>Speakers</h2>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Slug</th>
            <th>Short description</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="s in speakers" :key="s.id">
            <tr v-if="editingId !== s.id">
              <td>{{ displayName(s) }}</td>
              <td>{{ s.slug || '' }}</td>
              <td>{{ (s.short_description || '').slice(0, 60) }}{{ (s.short_description || '').length > 60 ? '…' : '' }}</td>
              <td>
                <button type="button" @click="startEdit(s)">Edit</button>
                <button type="button" @click="deleteSpeaker(s)">Delete</button>
              </td>
            </tr>
            <tr v-else class="editRow">
              <td>
                <input v-model="editFirstName" type="text">
                <input v-model="editSurname" type="text">
              </td>
              <td><input v-model="editSlug" type="text"></td>
              <td><textarea v-model="editShortDescription" rows="2"></textarea></td>
              <td>
                <button type="button" @click="saveEdit(s.id)">Save</button>
                <button type="button" @click="cancelEdit">Cancel</button>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
      <p v-if="speakers.length === 0 && !showLogin">No speakers. Add one above.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAdminAuth } from '../composables/useAdminAuth'

const { setAuth, clearAuth, apiFetch } = useAdminAuth()

const showLogin = ref(true)
const loginUser = ref('')
const loginPass = ref('')
const loginErr = ref('')
const err = ref('')
const speakers = ref([])

const newFirstName = ref('')
const newSurname = ref('')
const newSlug = ref('')
const newShortDescription = ref('')
const newBio = ref('')
const addStatus = ref('')
const addStatusClass = computed(() => (addStatus.value === 'Added.' ? 'ok' : addStatus.value ? 'err' : ''))

const editingId = ref(null)
const editFirstName = ref('')
const editSurname = ref('')
const editSlug = ref('')
const editShortDescription = ref('')

function displayName(p) {
  return (p.first_name && p.surname) ? `${p.first_name} ${p.surname}` : (p.display_name || p.id)
}

function loadSpeakers() {
  err.value = ''
  apiFetch('/api/admin/speakers')
    .then((r) => {
      if (r.status === 401) {
        showLogin.value = true
        return { _unauthorized: true }
      }
      return r.ok ? r.json() : Promise.reject(new Error(r.statusText))
    })
    .then((data) => {
      if (data && data._unauthorized) return
      showLogin.value = false
      speakers.value = Array.isArray(data) ? data : []
      editingId.value = null
    })
    .catch((e) => {
      err.value = 'Failed to load speakers: ' + e.message
      showLogin.value = true
    })
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
  loadSpeakers()
}

function addSpeaker() {
  const first = newFirstName.value.trim()
  const last = newSurname.value.trim()
  if (!first || !last) {
    addStatus.value = 'First name and surname required'
    return
  }
  addStatus.value = 'Adding...'
  apiFetch('/api/admin/speakers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      first_name: first,
      surname: last,
      slug: newSlug.value.trim() || null,
      short_description: newShortDescription.value.trim() || null,
      bio: newBio.value.trim() || null,
    }),
  })
    .then((r) => (r.ok ? r.json() : r.json().then((j) => Promise.reject(new Error(j.detail || r.statusText)))))
    .then(() => {
      newFirstName.value = ''
      newSurname.value = ''
      newSlug.value = ''
      newShortDescription.value = ''
      newBio.value = ''
      addStatus.value = 'Added.'
      loadSpeakers()
    })
    .catch((e) => {
      addStatus.value = e.message || (typeof e.detail === 'string' ? e.detail : 'Failed')
    })
}

function startEdit(s) {
  editingId.value = s.id
  editFirstName.value = s.first_name || ''
  editSurname.value = s.surname || ''
  editSlug.value = s.slug || ''
  editShortDescription.value = s.short_description || ''
}

function cancelEdit() {
  editingId.value = null
}

function saveEdit(id) {
  const first = editFirstName.value.trim()
  const last = editSurname.value.trim()
  if (!first || !last) {
    addStatus.value = 'First name and surname required'
    return
  }
  apiFetch('/api/admin/speakers/' + id, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      first_name: first,
      surname: last,
      slug: editSlug.value.trim() || null,
      short_description: editShortDescription.value.trim() || null,
    }),
  })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.statusText))))
    .then(() => loadSpeakers())
    .catch((e) => { addStatus.value = e.message })
}

function deleteSpeaker(s) {
  const name = displayName(s)
  if (!confirm(`Delete speaker "${name}"? All transcript mappings for this speaker will be removed.`)) return
  apiFetch('/api/admin/speakers/' + s.id, { method: 'DELETE' })
    .then((r) => {
      if (r.status === 404) throw new Error('Speaker not found')
      if (r.status !== 204) throw new Error(r.statusText)
      loadSpeakers()
    })
    .catch((e) => { addStatus.value = e.message })
}

onMounted(loadSpeakers)
</script>

<style scoped>
.login-box { background: #fff3cd; padding: 1rem; border-radius: 6px; margin-bottom: 1rem; }
.add-form { background: #f0f8ff; padding: 1rem; border-radius: 6px; margin-bottom: 1.5rem; }
.add-form input, .add-form textarea { max-width: 300px; }
.editRow td input, .editRow td textarea { width: 100%; max-width: 200px; box-sizing: border-box; }
</style>
