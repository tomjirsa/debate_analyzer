<template>
  <div>
    <p class="mb-3">
      <router-link to="/admin">← Admin</router-link>
    </p>

    <Card class="mb-4">
      <template #title>Create group</template>
      <template #content>
        <div class="flex flex-column gap-2" style="max-width: 400px;">
          <label for="newGroupName">Name</label>
          <InputText id="newGroupName" v-model="newName" placeholder="Group name" />
          <label for="newGroupSlug">Slug (URL-friendly)</label>
          <InputText id="newGroupSlug" v-model="newSlug" placeholder="my-group" />
          <label for="newGroupDesc">Description (optional)</label>
          <InputText id="newGroupDesc" v-model="newDescription" placeholder="Optional description" />
          <Button label="Create group" :loading="creating" :disabled="creating" @click="createGroup" />
          <Message v-if="createErr" severity="error">{{ createErr }}</Message>
          <Message v-else-if="createOk" severity="success">Group created.</Message>
        </div>
      </template>
    </Card>

    <Card>
      <template #title>Groups</template>
      <template #content>
        <Message v-if="listErr" severity="error">{{ listErr }}</Message>
        <DataTable
          v-else-if="groups.length"
          :value="groups"
          striped-rows
          responsive-layout="scroll"
          class="p-datatable-sm"
        >
          <Column field="name" header="Name" />
          <Column field="slug" header="Slug" />
          <Column field="description" header="Description">
            <template #body="{ data }">
              {{ (data.description || '').slice(0, 50) }}{{ (data.description || '').length > 50 ? '…' : '' }}
            </template>
          </Column>
          <Column header="Actions">
            <template #body="{ data }">
              <template v-if="editingId !== data.id">
                <Button label="Edit" text size="small" @click="startEdit(data)" />
                <Button label="Delete" severity="danger" text size="small" class="ml-1" @click="(e) => confirmDelete(e, data)" />
              </template>
              <template v-else>
                <div class="flex flex-wrap align-items-center gap-2">
                  <InputText v-model="editName" placeholder="Name" class="flex-1" style="min-width: 120px;" />
                  <InputText v-model="editSlug" placeholder="Slug" class="flex-1" style="min-width: 120px;" />
                  <InputText v-model="editDescription" placeholder="Description" class="flex-1" style="min-width: 160px;" />
                  <Button label="Save" size="small" @click="saveEdit(data.id)" />
                  <Button label="Cancel" text size="small" @click="cancelEdit" />
                  <Message v-if="editStatus" :severity="editStatus === 'Saved.' ? 'success' : 'error'">{{ editStatus }}</Message>
                </div>
              </template>
            </template>
          </Column>
        </DataTable>
        <p v-else>No groups. Create one above.</p>
      </template>
    </Card>

    <ConfirmPopup />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Column from 'primevue/column'
import ConfirmPopup from 'primevue/confirmpopup'
import DataTable from 'primevue/datatable'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import { useConfirm } from 'primevue/useconfirm'
import { useAdminAuth } from '../composables/useAdminAuth'

const router = useRouter()
const { clearAuth, apiFetch } = useAdminAuth()
const confirm = useConfirm()

const groups = ref([])
const listErr = ref('')
const newName = ref('')
const newSlug = ref('')
const newDescription = ref('')
const creating = ref(false)
const createErr = ref('')
const createOk = ref(false)

const editingId = ref(null)
const editName = ref('')
const editSlug = ref('')
const editDescription = ref('')
const editStatus = ref('')

function redirectToLogin() {
  clearAuth()
  router.push('/admin?expired=1')
}

function loadGroups() {
  listErr.value = ''
  apiFetch('/api/admin/groups')
    .then((r) => {
      if (r.status === 401) {
        redirectToLogin()
        return { _unauthorized: true }
      }
      return r.ok ? r.json() : Promise.reject(new Error(r.statusText))
    })
    .then((data) => {
      if (data && data._unauthorized) return
      groups.value = Array.isArray(data) ? data : []
      editingId.value = null
    })
    .catch((e) => { listErr.value = e.message })
}

function createGroup() {
  createErr.value = ''
  createOk.value = false
  const name = newName.value.trim()
  const slug = newSlug.value.trim()
  if (!name || !slug) {
    createErr.value = 'Name and slug are required.'
    return
  }
  creating.value = true
  apiFetch('/api/admin/groups', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name,
      slug,
      description: newDescription.value.trim() || null,
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
      if (data) {
        newName.value = ''
        newSlug.value = ''
        newDescription.value = ''
        createOk.value = true
        loadGroups()
      }
    })
    .catch((e) => { createErr.value = e.message || (e.detail || '') })
    .finally(() => { creating.value = false })
}

function startEdit(g) {
  editingId.value = g.id
  editName.value = g.name || ''
  editSlug.value = g.slug || ''
  editDescription.value = g.description || ''
  editStatus.value = ''
}

function cancelEdit() {
  editingId.value = null
  editStatus.value = ''
}

function saveEdit(id) {
  editStatus.value = ''
  apiFetch('/api/admin/groups/' + encodeURIComponent(id), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: editName.value.trim() || null,
      slug: editSlug.value.trim() || null,
      description: editDescription.value.trim() || null,
    }),
  })
    .then((r) => {
      if (r.status === 401) {
        redirectToLogin()
        return
      }
      return r.ok ? r.json() : r.json().then((j) => Promise.reject(new Error(j.detail || r.statusText)))
    })
    .then((updated) => {
      if (!updated) return
      const idx = groups.value.findIndex((x) => x.id === id)
      if (idx >= 0) groups.value[idx] = updated
      editingId.value = null
      editStatus.value = 'Saved.'
    })
    .catch((e) => { editStatus.value = e.message || (e.detail || '') })
}

function confirmDelete(event, g) {
  confirm.require({
    target: event.currentTarget,
    message: 'Delete group "' + (g.name || g.slug) + '"? This only works if the group has no transcripts and no speakers.',
    accept: () => {
      apiFetch('/api/admin/groups/' + encodeURIComponent(g.id), { method: 'DELETE' })
        .then((r) => {
          if (r.status === 401) {
            redirectToLogin()
            return
          }
          if (r.status === 404) throw new Error('Group not found')
          if (r.status === 400) throw new Error(r.statusText || 'Cannot delete: group has transcripts or speakers')
          if (r.status !== 204) throw new Error(r.statusText)
          loadGroups()
        })
        .catch((e) => { listErr.value = e.message })
    },
  })
}

onMounted(loadGroups)
</script>

<style scoped>
.mb-3 { margin-bottom: 1rem; }
.mb-4 { margin-bottom: 1.5rem; }
.ml-1 { margin-left: 0.25rem; }
</style>
