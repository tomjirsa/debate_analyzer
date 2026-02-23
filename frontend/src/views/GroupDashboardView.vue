<template>
  <div>
    <Breadcrumb :model="breadcrumbItems" class="mb-3">
      <template #item="{ item }">
        <router-link v-if="item.to" :to="item.to" class="p-menuitem-link">{{ item.label }}</router-link>
        <span v-else>{{ item.label }}</span>
      </template>
    </Breadcrumb>

    <Card v-if="group" class="mb-3">
      <template #title>{{ group.name }}</template>
      <template #subtitle>{{ group.description || 'Group dashboard' }}</template>
      <template #content>
        <ProgressSpinner v-if="loading" aria-label="Loading" />
        <Message v-else-if="error" id="loadErr" severity="error">{{ error }}</Message>
        <template v-else>
          <p class="dashboard-stats">
            {{ transcripts.length }} transcript{{ transcripts.length === 1 ? '' : 's' }},
            {{ speakers.length }} speaker{{ speakers.length === 1 ? '' : 's' }}
          </p>
        </template>
      </template>
    </Card>

    <Card v-if="group && !loading && !error" class="mb-3">
      <template #title>Transcripts</template>
      <template #content>
        <Message v-if="!transcripts.length" severity="info">
          No transcripts in this group yet. Add them in the admin.
        </Message>
        <ul v-else id="transcripts" class="transcript-list">
          <li v-for="t in transcripts" :key="t.id">
            <a :href="transcriptLink(t)" target="_blank" rel="noopener noreferrer">
              {{ t.title || t.source_uri || t.id }}
            </a>
            <span v-if="t.created_at" class="transcript-date">{{ formatDate(t.created_at) }}</span>
          </li>
        </ul>
      </template>
    </Card>

    <Card v-if="group && !loading && !error">
      <template #title>Speakers</template>
      <template #content>
        <Message v-if="!speakers.length" severity="info">
          No speakers in this group yet. Add transcripts and assign speakers in the admin.
        </Message>
        <ul v-else id="speakers" class="speaker-list">
          <li v-for="s in speakers" :key="s.id">
            <router-link :to="speakerLink(s)">
              {{ displayName(s) }}
            </router-link>
          </li>
        </ul>
      </template>
    </Card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import Card from 'primevue/card'
import Message from 'primevue/message'
import ProgressSpinner from 'primevue/progressspinner'
import Breadcrumb from 'primevue/breadcrumb'

const route = useRoute()
const groupIdOrSlug = computed(() => route.params.idOrSlug)

const group = ref(null)
const speakers = ref([])
const transcripts = ref([])
const loading = ref(true)
const error = ref('')

const breadcrumbItems = computed(() => {
  const items = [{ label: 'Dashboard', to: '/' }]
  if (group.value) {
    items.push({ label: group.value.name })
  }
  return items
})

function displayName(s) {
  if (s.first_name && s.surname) return `${s.first_name} ${s.surname}`
  return s.display_name || s.id
}

function speakerLink(s) {
  const g = groupIdOrSlug.value
  const id = (s.slug || s.id)
  return `/group/${encodeURIComponent(g)}/speakers/${encodeURIComponent(id)}`
}

function transcriptLink(t) {
  return `/admin/annotate?transcript_id=${encodeURIComponent(t.id)}`
}

function formatDate(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleDateString(undefined, { dateStyle: 'medium' })
  } catch (_) {
    return iso
  }
}

async function load() {
  if (!groupIdOrSlug.value) return
  loading.value = true
  error.value = ''
  try {
    const gr = await fetch('/api/groups/' + encodeURIComponent(groupIdOrSlug.value))
    if (!gr.ok) throw new Error(gr.status === 404 ? 'Group not found' : gr.statusText)
    group.value = await gr.json()
    const [sr, tr] = await Promise.all([
      fetch('/api/groups/' + encodeURIComponent(groupIdOrSlug.value) + '/speakers'),
      fetch('/api/groups/' + encodeURIComponent(groupIdOrSlug.value) + '/transcripts'),
    ])
    if (!sr.ok) throw new Error(sr.statusText)
    if (!tr.ok) throw new Error(tr.statusText)
    speakers.value = await sr.json()
    transcripts.value = await tr.json()
  } catch (e) {
    error.value = e.message
    group.value = null
    speakers.value = []
    transcripts.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(groupIdOrSlug, load)
</script>

<style scoped>
.dashboard-stats { margin: 0; font-size: 1rem; }
.speaker-list, .transcript-list { list-style: none; padding: 0; margin: 0; }
.speaker-list li, .transcript-list li { margin: 0.5rem 0; }
.speaker-list a, .transcript-list a { text-decoration: none; }
.speaker-list a:hover, .transcript-list a:hover { text-decoration: underline; }
.transcript-date { margin-left: 0.5rem; font-size: 0.9rem; color: var(--p-text-muted-color, #6b7280); }
.mb-3 { margin-bottom: 1rem; }
</style>
