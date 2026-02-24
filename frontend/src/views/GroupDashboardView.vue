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
      <template #title>Speakers</template>
      <template #content>
        <Message v-if="!speakers.length" severity="info">
          No speakers in this group yet. Add transcripts and assign speakers in the admin.
        </Message>
        <div v-else class="speaker-cards">
          <router-link
            v-for="s in speakers"
            :key="s.id"
            :to="speakerLink(s)"
            class="speaker-card"
          >
            <div class="speaker-card-header">
              <Avatar
                v-if="s.photo_url"
                :image="s.photo_url"
                shape="circle"
                size="xlarge"
                class="speaker-card-avatar"
              />
              <Avatar
                v-else
                :label="initials(s)"
                shape="circle"
                size="xlarge"
                class="speaker-card-avatar"
              />
              <span class="speaker-card-name">{{ displayName(s) }}</span>
            </div>
            <div class="speaker-card-body">
              <p v-if="s.short_description" class="speaker-card-desc">{{ s.short_description }}</p>
              <p v-if="s.bio && !s.short_description" class="speaker-card-desc speaker-card-bio-excerpt">{{ bioExcerpt(s.bio) }}</p>
              <div class="speaker-card-stats">
                <span class="speaker-card-stat">
                  <span class="speaker-card-stat-value">{{ s.transcript_count ?? 0 }}</span>
                  <span class="speaker-card-stat-label">transcript{{ (s.transcript_count ?? 0) === 1 ? '' : 's' }}</span>
                </span>
              </div>
            </div>
          </router-link>
        </div>
      </template>
    </Card>

    <Card v-if="group && !loading && !error">
      <template #title>Transcripts</template>
      <template #content>
        <Message v-if="!transcripts.length" severity="info">
          No transcripts in this group yet. Add them in the admin.
        </Message>
        <DataTable v-else id="transcripts" :value="transcripts" data-key="id" class="dashboard-table">
          <Column field="title" header="Name" sortable>
            <template #body="{ data }">
              <router-link :to="transcriptLink(data)">
                {{ data.title || data.source_uri || data.id }}
              </router-link>
            </template>
          </Column>
          <Column field="debate_date" header="Debate date" sortable>
            <template #body="{ data }">
              {{ data.debate_date ? formatDate(data.debate_date) : '—' }}
            </template>
          </Column>
          <Column field="description" header="Description" sortable>
            <template #body="{ data }">
              <span class="cell-truncate" :title="data.description">{{ (data.description || '').slice(0, 60) }}{{ (data.description || '').length > 60 ? '…' : '' }}</span>
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import Avatar from 'primevue/avatar'
import Breadcrumb from 'primevue/breadcrumb'
import Card from 'primevue/card'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Message from 'primevue/message'
import ProgressSpinner from 'primevue/progressspinner'

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

function initials(s) {
  const a = (s.first_name || '').trim().slice(0, 1)
  const b = (s.surname || '').trim().slice(0, 1)
  return (a + b).toUpperCase() || '?'
}

function bioExcerpt(bio, maxLen = 100) {
  if (!bio || typeof bio !== 'string') return ''
  const t = bio.trim()
  if (t.length <= maxLen) return t
  return t.slice(0, maxLen).trim() + '…'
}

function speakerLink(s) {
  const g = groupIdOrSlug.value
  const id = (s.slug || s.id)
  return `/group/${encodeURIComponent(g)}/speakers/${encodeURIComponent(id)}`
}

function transcriptLink(t) {
  const g = groupIdOrSlug.value
  return `/group/${encodeURIComponent(g)}/transcripts/${encodeURIComponent(t.id)}`
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
.dashboard-table { margin-top: 0.25rem; }
.dashboard-table a { text-decoration: none; }
.dashboard-table a:hover { text-decoration: underline; }
.cell-truncate { display: inline-block; max-width: 20rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* Speaker cards: business-card style, Pico-inspired clean layout */
.speaker-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 1.5rem;
}
.speaker-card {
  display: flex;
  flex-direction: column;
  text-decoration: none;
  color: inherit;
  background: var(--p-surface-0, #fff);
  border: 1px solid var(--p-surface-200, #e5e7eb);
  border-radius: 12px;
  overflow: hidden;
  transition: box-shadow 0.2s ease, transform 0.2s ease, border-color 0.2s ease;
}
.speaker-card:hover {
  border-color: var(--p-primary-color, #3b82f6);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08), 0 2px 6px rgba(0, 0, 0, 0.04);
  transform: translateY(-2px);
}
.speaker-card-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 1.5rem 1.25rem 0.75rem;
  background: linear-gradient(180deg, var(--p-surface-50, #f9fafb) 0%, var(--p-surface-0, #fff) 100%);
  border-bottom: 1px solid var(--p-surface-100, #f3f4f6);
}
.speaker-card-avatar {
  flex-shrink: 0;
  margin-bottom: 0.75rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.speaker-card-name {
  font-weight: 600;
  font-size: 1.1rem;
  text-align: center;
  line-height: 1.3;
}
.speaker-card-body {
  padding: 1rem 1.25rem 1.25rem;
  min-width: 0;
}
.speaker-card-desc {
  margin: 0 0 0.75rem;
  font-size: 0.875rem;
  color: var(--p-text-color-secondary, #6b7280);
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.speaker-card-bio-excerpt {
  font-style: italic;
}
.speaker-card-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-top: 0.5rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--p-surface-100, #f3f4f6);
}
.speaker-card-stat {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}
.speaker-card-stat-value {
  font-weight: 700;
  font-size: 1.25rem;
  color: var(--p-primary-color, #3b82f6);
  line-height: 1.2;
}
.speaker-card-stat-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.02em;
  color: var(--p-text-color-secondary, #6b7280);
}

.mb-3 { margin-bottom: 1rem; }
</style>
