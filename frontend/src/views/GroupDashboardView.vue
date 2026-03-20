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
      <template #title>At a glance</template>
      <template #content>
        <MetricStatGrid :items="atAGlanceItems" />
      </template>
    </Card>

    <Card v-if="group && !loading && !error" class="mb-3">
      <template #title>Top speakers</template>
      <template #content>
        <Message v-if="!topSpeakers.length" severity="info">
          No speakers in this group yet.
        </Message>
        <template v-else>
          <div class="dashboard-chart-section">
            <div class="dashboard-chart-header">
              <span>By transcript count</span>
            </div>
            <StatBarChart
              :labels="topSpeakerLabels"
              :values="topSpeakerValues"
              yAxisName="Transcripts"
              :value-formatter="transcriptCountFormatter"
            />
          </div>
        </template>
      </template>
    </Card>

    <Card v-if="group && !loading && !error" class="mb-3">
      <template #title>Speakers</template>
      <template #content>
        <Message v-if="!speakers.length" severity="info">
          No speakers in this group yet. Add transcripts and assign speakers in the admin.
        </Message>
        <DataTable
          v-else
          id="speakers"
          :value="speakers"
          data-key="id"
          responsive-layout="scroll"
          class="dashboard-table p-datatable-sm"
        >
          <Column header="Photo">
            <template #body="{ data }">
              <router-link :to="speakerLink(data)" class="speaker-photo-link">
                <Avatar
                  v-if="data.photo_url"
                  :image="data.photo_url"
                  shape="circle"
                  size="large"
                />
                <Avatar v-else :label="initials(data)" shape="circle" size="large" />
              </router-link>
            </template>
          </Column>

          <Column header="Speaker">
            <template #body="{ data }">
              <router-link :to="speakerLink(data)">
                {{ displayName(data) }}
              </router-link>
            </template>
          </Column>

          <Column header="Bio / Description">
            <template #body="{ data }">
              <span
                class="cell-truncate"
                :title="data.short_description || data.bio || ''"
              >
                {{ data.short_description || bioExcerpt(data.bio) || '—' }}
              </span>
            </template>
          </Column>

          <Column field="transcript_count" header="Transcripts" sortable>
            <template #body="{ data }">
              {{ data.transcript_count ?? 0 }}
            </template>
          </Column>
        </DataTable>
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
import MetricStatGrid from '../components/MetricStatGrid.vue'
import StatBarChart from '../components/StatBarChart.vue'

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

const atAGlanceItems = computed(() => {
  const transcriptCount = transcripts.value?.length ?? 0
  const speakerCount = speakers.value?.length ?? 0
  const totalSpeakerTranscriptCount = (speakers.value || []).reduce(
    (acc, s) => acc + (Number(s.transcript_count) || 0),
    0,
  )
  const topSpeakerTranscriptCount = (speakers.value || []).reduce(
    (max, s) => Math.max(max, Number(s.transcript_count) || 0),
    0,
  )
  return [
    { key: 'transcripts', value: transcriptCount, label: 'Transcripts' },
    { key: 'speakers', value: speakerCount, label: 'Speakers' },
    { key: 'links', value: totalSpeakerTranscriptCount, label: 'Speaker-transcript links' },
    { key: 'top', value: topSpeakerTranscriptCount, label: 'Top speaker transcripts' },
  ]
})

const topSpeakers = computed(() => {
  const list = (speakers.value || []).map((s) => ({
    id: s.id,
    name: displayName(s),
    count: Number(s.transcript_count) || 0,
  }))
  list.sort((a, b) => b.count - a.count)
  return list.slice(0, 5)
})

const topSpeakerLabels = computed(() =>
  (topSpeakers.value || []).map((s) => {
    const maxLen = 24
    if (s.name.length <= maxLen) return s.name
    return s.name.slice(0, maxLen - 1) + '…'
  }),
)

const topSpeakerValues = computed(() => (topSpeakers.value || []).map((s) => s.count))

function transcriptCountFormatter(value) {
  const n = Number(value)
  if (Number.isNaN(n)) return '—'
  return n.toLocaleString()
}

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

/* Speaker table: keep photo cell compact and centered. */
.speaker-photo-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 3rem;
}

.mb-3 { margin-bottom: 1rem; }
</style>
