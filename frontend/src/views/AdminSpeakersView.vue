<template>
  <div>
    <p class="mb-3">
      <router-link to="/admin">← Admin</router-link>
    </p>

    <Card class="mb-4">
        <template #title>Add speaker</template>
        <template #content>
          <div class="flex flex-column gap-2" style="max-width: 400px;">
            <div class="flex flex-column gap-1 w-full">
              <label>Group</label>
              <Select
                v-model="selectedGroupId"
                :options="groups"
                option-label="name"
                option-value="id"
                placeholder="Select group"
                class="w-full"
              />
            </div>
            <div class="flex flex-column gap-1 w-full">
              <label>First name</label>
              <InputText v-model="newFirstName" placeholder="First name" class="w-full" />
            </div>
            <div class="flex flex-column gap-1 w-full">
              <label>Surname</label>
              <InputText v-model="newSurname" placeholder="Surname" class="w-full" />
            </div>
            <div class="flex flex-column gap-1 w-full">
              <label>Slug (optional)</label>
              <InputText v-model="newSlug" placeholder="url-slug" class="w-full" />
            </div>
            <div class="flex gap-2 w-full align-items-start">
              <label class="flex-shrink-0 pt-2" style="min-width: 11em;">Short description (optional)</label>
              <Textarea v-model="newShortDescription" placeholder="Short description" rows="3" class="flex-1 w-full" />
            </div>
            <div class="flex gap-2 w-full align-items-start">
              <label class="flex-shrink-0 pt-2" style="min-width: 11em;">Bio (optional)</label>
              <Textarea v-model="newBio" placeholder="Bio" rows="3" class="flex-1 w-full" />
            </div>
            <Button label="Add speaker" @click="addSpeaker" />
            <Message v-if="addStatus" :severity="addStatus === 'Added.' ? 'success' : 'error'">{{ addStatus }}</Message>
          </div>
        </template>
      </Card>

      <Card>
        <template #title>Speakers</template>
        <template #content>
          <Message v-if="err" severity="error">{{ err }}</Message>
          <Message v-else-if="uploadStatus" :severity="uploadStatus === 'Uploaded.' ? 'success' : 'info'">{{ uploadStatus }}</Message>
          <DataTable
            v-else-if="speakers.length"
            :value="speakers"
            striped-rows
            responsive-layout="scroll"
            class="p-datatable-sm"
          >
            <Column header="Photo" style="width: 80px;">
              <template #body="{ data }">
                <div class="flex align-items-center gap-2">
                  <Avatar
                    v-if="data.photo_url"
                    :image="data.photo_url"
                    shape="circle"
                    size="normal"
                    class="speaker-photo-thumb"
                  />
                  <Avatar
                    v-else
                    :label="initials(data)"
                    shape="circle"
                    size="normal"
                    class="speaker-photo-thumb"
                  />
                  <span v-if="editingId !== data.id" class="flex flex-column gap-1">
                    <Button label="Upload" text size="small" @click="triggerUpload(data.id)" />
                    <Button
                      v-if="data.photo_key"
                      label="Remove"
                      text size="small"
                      severity="secondary"
                      @click="removePhoto(data)"
                    />
                  </span>
                </div>
              </template>
            </Column>
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

    <input
      ref="fileInputRef"
      type="file"
      accept="image/jpeg,image/png,image/webp"
      class="hidden"
      @change="onFileSelected"
    />
    <ConfirmPopup />
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import Avatar from 'primevue/avatar'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Column from 'primevue/column'
import ConfirmPopup from 'primevue/confirmpopup'
import DataTable from 'primevue/datatable'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Textarea from 'primevue/textarea'
import { useConfirm } from 'primevue/useconfirm'
import { useAdminAuth } from '../composables/useAdminAuth'

const router = useRouter()
const { clearAuth, apiFetch } = useAdminAuth()
const confirm = useConfirm()

const groups = ref([])
const selectedGroupId = ref(null)
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

const fileInputRef = ref(null)
const uploadTargetId = ref(null)
const uploadStatus = ref('')

const ALLOWED_EXT = ['jpg', 'jpeg', 'png', 'webp']

function displayName(p) {
  return (p.first_name && p.surname) ? `${p.first_name} ${p.surname}` : (p.display_name || p.id)
}

function initials(p) {
  const a = (p.first_name || '').trim().slice(0, 1)
  const b = (p.surname || '').trim().slice(0, 1)
  return (a + b).toUpperCase() || '?'
}

function triggerUpload(speakerId) {
  uploadTargetId.value = speakerId
  uploadStatus.value = ''
  fileInputRef.value?.click()
}

function onFileSelected(event) {
  const file = event.target.files?.[0]
  const id = uploadTargetId.value
  if (!file || !id) return
  event.target.value = ''
  uploadTargetId.value = null
  const ext = (file.name.split('.').pop() || 'jpg').toLowerCase()
  const safeExt = ALLOWED_EXT.includes(ext) ? ext : 'jpg'
  uploadStatus.value = 'Uploading...'
  apiFetch('/api/admin/speakers/' + id + '/photo-upload-url?ext=' + encodeURIComponent(safeExt))
    .then((r) => {
      if (r.status === 401) {
        redirectToLogin()
        return null
      }
      return r.ok ? r.json() : Promise.reject(new Error(r.statusText))
    })
    .then((data) => {
      if (!data?.put_url || !data?.key) throw new Error('Invalid upload URL response')
      return fetch(data.put_url, {
        method: 'PUT',
        body: file,
        headers: { 'Content-Type': file.type || 'image/jpeg' },
      }).then((res) => {
        if (!res.ok) throw new Error('Upload failed')
        return data.key
      })
    })
    .then((key) => {
      return apiFetch('/api/admin/speakers/' + id, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ photo_key: key }),
      })
    })
    .then((r) => {
      if (r.status === 401) { redirectToLogin(); return }
      if (!r.ok) throw new Error(r.statusText)
      uploadStatus.value = 'Uploaded.'
      loadSpeakers()
    })
    .catch((e) => { uploadStatus.value = e.message || 'Failed' })
}

function removePhoto(data) {
  apiFetch('/api/admin/speakers/' + data.id, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ photo_key: null }),
  })
    .then((r) => {
      if (r.status === 401) { redirectToLogin(); return }
      if (!r.ok) throw new Error(r.statusText)
      loadSpeakers()
    })
    .catch((e) => { addStatus.value = e.message })
}

function redirectToLogin() {
  clearAuth()
  router.push('/admin?expired=1')
}

function loadGroups() {
  return apiFetch('/api/admin/groups')
    .then((r) => (r.ok ? r.json() : []))
    .then((data) => {
      groups.value = Array.isArray(data) ? data : []
      if (groups.value.length && !selectedGroupId.value) {
        selectedGroupId.value = groups.value[0].id
      }
    })
    .catch(() => {})
}

function loadSpeakers() {
  err.value = ''
  const url = selectedGroupId.value
    ? '/api/admin/speakers?group_id=' + encodeURIComponent(selectedGroupId.value)
    : '/api/admin/speakers'
  apiFetch(url)
    .then((r) => {
      if (r.status === 401) {
        redirectToLogin()
        return { _unauthorized: true }
      }
      return r.ok ? r.json() : Promise.reject(new Error(r.statusText))
    })
    .then((data) => {
      if (data && data._unauthorized) return
      speakers.value = Array.isArray(data) ? data : []
      editingId.value = null
    })
    .catch((e) => {
      err.value = 'Failed to load speakers: ' + e.message
    })
}

function addSpeaker() {
  const first = newFirstName.value.trim()
  const last = newSurname.value.trim()
  if (!first || !last) {
    addStatus.value = 'First name and surname required'
    return
  }
  if (!selectedGroupId.value) {
    addStatus.value = 'Select a group'
    return
  }
  addStatus.value = 'Adding...'
  apiFetch('/api/admin/speakers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      first_name: first,
      surname: last,
      group_id: selectedGroupId.value,
      slug: newSlug.value.trim() || null,
      short_description: newShortDescription.value.trim() || null,
      bio: newBio.value.trim() || null,
    }),
  })
    .then((r) => {
      if (r.status === 401) {
        redirectToLogin()
        return
      }
      return r.ok ? r.json() : r.json().then((j) => Promise.reject(new Error(j.detail || r.statusText)))
    })
    .then((data) => {
      if (!data) return
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
    .then((r) => {
      if (r.status === 401) {
        redirectToLogin()
        return
      }
      return r.ok ? r.json() : Promise.reject(new Error(r.statusText))
    })
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
          if (r.status === 401) {
            redirectToLogin()
            return
          }
          if (r.status === 404) throw new Error('Speaker not found')
          if (r.status !== 204) throw new Error(r.statusText)
          loadSpeakers()
        })
        .catch((e) => { addStatus.value = e.message })
    },
  })
}

onMounted(() => {
  loadGroups().then(loadSpeakers)
})
watch(selectedGroupId, () => { loadSpeakers() })
</script>

<style scoped>
.mb-3 { margin-bottom: 1rem; }
.mb-4 { margin-bottom: 1.5rem; }
.ml-1 { margin-left: 0.25rem; }
.hidden { position: absolute; opacity: 0; width: 0; height: 0; pointer-events: none; }
.speaker-photo-thumb { flex-shrink: 0; }
</style>
