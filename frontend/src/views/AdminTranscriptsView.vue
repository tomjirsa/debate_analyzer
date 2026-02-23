<template>
  <div>
    <p class="mb-3">
      <router-link to="/admin">← Admin</router-link>
      | <router-link to="/admin/speakers">Manage speakers</router-link>
    </p>

    <Card class="mb-4">
        <template #title>Register transcript</template>
        <template #content>
          <p>Enter S3 URI (e.g. <code>s3://bucket/jobs/xxx/transcripts/file.json</code>) or local path.</p>
          <div class="flex flex-column gap-2" style="max-width: 480px;">
            <label for="sourceUri">Source URI or path</label>
            <InputText id="sourceUri" v-model="sourceUri" placeholder="s3://... or path" />
            <label for="title">Title (optional)</label>
            <InputText id="title" v-model="title" placeholder="Optional display title" />
            <Button label="Register" :loading="registering" :disabled="registering" @click="register" />
            <Message v-if="registerErr" severity="error">{{ registerErr }}</Message>
          </div>
        </template>
      </Card>

      <Card>
        <template #title>Transcripts</template>
        <template #content>
          <Message v-if="listErr" severity="error">{{ listErr }}</Message>
          <DataTable
            v-else-if="transcripts.length"
            :value="transcripts"
            striped-rows
            responsive-layout="scroll"
            class="p-datatable-sm"
          >
            <Column field="title" header="Title">
              <template #body="{ data }">
                {{ data.title || '—' }}
              </template>
            </Column>
            <Column field="source_uri" header="Source URI">
              <template #body="{ data }">
                <span class="uri-cell">{{ data.source_uri }}</span>
              </template>
            </Column>
            <Column field="speakers_count" header="Speakers">
              <template #body="{ data }">
                {{ data.speakers_count ?? '—' }}
              </template>
            </Column>
            <Column field="created_at" header="Created">
              <template #body="{ data }">
                {{ formatDate(data.created_at) }}
              </template>
            </Column>
            <Column header="Actions">
              <template #body="{ data }">
                <template v-if="editingId !== data.id">
                  <router-link :to="'/admin/annotate?transcript_id=' + encodeURIComponent(data.id)" class="action-link">Annotate</router-link>
                  <Button label="Edit" text size="small" class="ml-1" @click="startEdit(data)" />
                  <Button label="Delete" severity="danger" text size="small" class="ml-1" @click="(e) => confirmDelete(e, data)" />
                </template>
                <template v-else>
                  <div class="flex flex-wrap align-items-center gap-2">
                    <InputText v-model="editTitle" placeholder="Title" class="flex-1" style="min-width: 120px;" />
                    <InputText v-model="editVideoPath" placeholder="Video path (optional)" class="flex-1" style="min-width: 180px;" />
                    <Button label="Save" size="small" @click="saveEdit(data.id)" />
                    <Button label="Cancel" text size="small" @click="cancelEdit" />
                    <Message v-if="editStatus" :severity="editStatus === 'Saved.' ? 'success' : 'error'">{{ editStatus }}</Message>
                  </div>
                </template>
              </template>
            </Column>
          </DataTable>
          <p v-else>No transcripts. Register one above.</p>
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

function formatDate(iso) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleDateString(undefined, { dateStyle: 'short' })
  } catch (_) {
    return iso
  }
}

function redirectToLogin() {
  clearAuth()
  router.push('/admin?expired=1')
}

function loadTranscripts() {
  listErr.value = ''
  apiFetch('/api/admin/transcripts')
    .then((r) => {
      if (r.status === 401) {
        redirectToLogin()
        return { _unauthorized: true }
      }
      return r.ok ? r.json() : Promise.reject(new Error(r.statusText))
    })
    .then((data) => {
      if (data && data._unauthorized) return
      transcripts.value = Array.isArray(data) ? data : []
      editingId.value = null
    })
    .catch((e) => { listErr.value = e.message })
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
    .then((r) => {
      if (r.status === 401) {
        redirectToLogin()
        return
      }
      return r.ok ? r.json() : r.json().then((j) => Promise.reject(new Error(j.detail || r.statusText)))
    })
    .then((data) => {
      if (data) {
        sourceUri.value = ''
        title.value = ''
        loadTranscripts()
      }
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
    .then((r) => {
      if (r.status === 401) {
        redirectToLogin()
        return
      }
      return r.ok ? r.json() : r.json().then((j) => Promise.reject(new Error(j.detail || r.statusText)))
    })
    .then((updated) => {
      if (!updated) return
      const idx = transcripts.value.findIndex((x) => x.id === id)
      if (idx >= 0) transcripts.value[idx] = updated
      editingId.value = null
      editStatus.value = 'Saved.'
    })
    .catch((e) => { editStatus.value = e.message || (e.detail || '') })
}

function confirmDelete(event, t) {
  const name = t.title || t.source_uri || t.id
  confirm.require({
    target: event.currentTarget,
    message: 'Delete this transcript? Segments and speaker mappings will be removed.\n\n' + name,
    accept: () => {
      apiFetch('/api/admin/transcripts/' + t.id, { method: 'DELETE' })
        .then((r) => {
          if (r.status === 401) {
            redirectToLogin()
            return
          }
          if (r.status === 404) throw new Error('Transcript not found')
          if (r.status !== 204) throw new Error(r.statusText)
          loadTranscripts()
        })
        .catch((e) => { listErr.value = e.message })
    },
  })
}

onMounted(loadTranscripts)
</script>

<style scoped>
.mb-3 { margin-bottom: 1rem; }
.mb-4 { margin-bottom: 1.5rem; }
.ml-1 { margin-left: 0.25rem; }
.action-link { margin-right: 0.25rem; text-decoration: none; }
.action-link:hover { text-decoration: underline; }
.uri-cell {
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: inline-block;
}
</style>
