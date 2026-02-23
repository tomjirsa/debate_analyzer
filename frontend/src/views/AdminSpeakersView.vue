<template>
  <div>
    <p class="mb-3">
      <router-link to="/admin">← Admin</router-link>
    </p>

    <Card v-if="showLogin">
      <template #title>Admin login</template>
      <template #content>
        <p>Log in to manage speakers. You can also <router-link to="/admin">log in on the Admin page</router-link> first.</p>
        <div class="flex flex-column gap-2" style="max-width: 320px;">
          <label for="loginUser">Username</label>
          <InputText id="loginUser" v-model="loginUser" placeholder="username" autocomplete="username" />
          <label for="loginPass">Password</label>
          <Password id="loginPass" v-model="loginPass" placeholder="password" :feedback="false" toggle-mask input-class="w-full" />
          <Button label="Log in" @click="doLogin" />
          <Message v-if="loginErr" severity="error">{{ loginErr }}</Message>
        </div>
      </template>
    </Card>

    <template v-else>
      <Card class="mb-4">
        <template #title>Add speaker</template>
        <template #content>
          <div class="flex flex-column gap-2" style="max-width: 400px;">
            <label>First name</label>
            <InputText v-model="newFirstName" placeholder="First name" />
            <label>Surname</label>
            <InputText v-model="newSurname" placeholder="Surname" />
            <label>Slug (optional)</label>
            <InputText v-model="newSlug" placeholder="url-slug" />
            <label>Short description (optional)</label>
            <Textarea v-model="newShortDescription" placeholder="Short description" rows="3" />
            <label>Bio (optional)</label>
            <Textarea v-model="newBio" placeholder="Bio" rows="3" />
            <Button label="Add speaker" @click="addSpeaker" />
            <Message v-if="addStatus" :severity="addStatus === 'Added.' ? 'success' : 'error'">{{ addStatus }}</Message>
          </div>
        </template>
      </Card>

      <Card>
        <template #title>Speakers</template>
        <template #content>
          <Message v-if="err" severity="error">{{ err }}</Message>
          <DataTable
            v-else-if="speakers.length"
            :value="speakers"
            striped-rows
            responsive-layout="scroll"
            class="p-datatable-sm"
          >
            <Column header="Name">
              <template #body="{ data }">
                <template v-if="editingId !== data.id">
                  {{ displayName(data) }}
                </template>
                <template v-else>
                  <div class="flex gap-2">
                    <InputText v-model="editFirstName" placeholder="First name" class="flex-1" style="min-width: 100px;" />
                    <InputText v-model="editSurname" placeholder="Surname" class="flex-1" style="min-width: 100px;" />
                  </div>
                </template>
              </template>
            </Column>
            <Column header="Slug">
              <template #body="{ data }">
                <template v-if="editingId !== data.id">
                  {{ data.slug || '' }}
                </template>
                <template v-else>
                  <InputText v-model="editSlug" placeholder="Slug" style="min-width: 120px;" />
                </template>
              </template>
            </Column>
            <Column header="Short description">
              <template #body="{ data }">
                <template v-if="editingId !== data.id">
                  {{ (data.short_description || '').slice(0, 60) }}{{ (data.short_description || '').length > 60 ? '…' : '' }}
                </template>
                <template v-else>
                  <Textarea v-model="editShortDescription" rows="2" style="min-width: 200px;" />
                </template>
              </template>
            </Column>
            <Column header="Actions">
              <template #body="{ data }">
                <template v-if="editingId !== data.id">
                  <Button label="Edit" text size="small" @click="startEdit(data)" />
                  <Button label="Delete" severity="danger" text size="small" class="ml-1" @click="(e) => confirmDelete(e, data)" />
                </template>
                <template v-else>
                  <Button label="Save" size="small" @click="saveEdit(data.id)" />
                  <Button label="Cancel" text size="small" class="ml-1" @click="cancelEdit" />
                </template>
              </template>
            </Column>
          </DataTable>
          <p v-else>No speakers. Add one above.</p>
        </template>
      </Card>
    </template>

    <ConfirmPopup />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Column from 'primevue/column'
import ConfirmPopup from 'primevue/confirmpopup'
import DataTable from 'primevue/datatable'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Password from 'primevue/password'
import Textarea from 'primevue/textarea'
import { useConfirm } from 'primevue/useconfirm'
import { useAdminAuth } from '../composables/useAdminAuth'

const { setAuth, clearAuth, apiFetch } = useAdminAuth()
const confirm = useConfirm()

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

function confirmDelete(event, s) {
  const name = displayName(s)
  confirm.require({
    target: event.currentTarget,
    message: `Delete speaker "${name}"? All transcript mappings for this speaker will be removed.`,
    accept: () => {
      apiFetch('/api/admin/speakers/' + s.id, { method: 'DELETE' })
        .then((r) => {
          if (r.status === 404) throw new Error('Speaker not found')
          if (r.status !== 204) throw new Error(r.statusText)
          loadSpeakers()
        })
        .catch((e) => { addStatus.value = e.message })
    },
  })
}

onMounted(loadSpeakers)
</script>

<style scoped>
.mb-3 { margin-bottom: 1rem; }
.mb-4 { margin-bottom: 1.5rem; }
.ml-1 { margin-left: 0.25rem; }
</style>
