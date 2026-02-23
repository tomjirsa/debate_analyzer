<template>
  <div>
    <Breadcrumb :model="breadcrumbItems" class="mb-3">
      <template #item="{ item }">
        <a
          v-if="item.command"
          href="#"
          class="p-menuitem-link"
          @click="(e) => { e.preventDefault(); item.command({ originalEvent: e }) }"
        >{{ item.label }}</a>
        <span v-else>{{ item.label }}</span>
      </template>
    </Breadcrumb>

    <Message v-if="error" severity="error">{{ error }}</Message>

    <template v-else-if="profile">
      <Card class="mb-4">
        <template #title>{{ displayName }}</template>
        <template #subtitle>{{ profile.short_description || '' }}</template>
        <template #content>
          <p v-if="profile.bio">{{ profile.bio }}</p>
        </template>
      </Card>

      <Card class="mb-4">
        <template #title>Summary</template>
        <template #content>
          <template v-if="statDefinitions.length">
            <section v-for="group in statDefinitions" :key="group.key" class="stat-group">
              <h3 class="group-label">{{ group.label }}</h3>
              <div class="stats">
                <div
                  v-for="defn in group.stats"
                  :key="defn.stat_key"
                  v-show="stats[defn.stat_key] != null && stats[defn.stat_key] !== ''"
                  class="stat"
                >
                  <span class="value">{{ formatStatValue(defn.stat_key, stats[defn.stat_key]) }}</span>
                  <br><span class="label">{{ statLabel(defn.stat_key, defn.label, stats[defn.stat_key]) }}</span>
                </div>
              </div>
            </section>
          </template>
          <template v-else>
            <div class="stats">
              <div class="stat">
                <span class="value">{{ formatNum(stats.transcript_count) }}</span>
                <br><span class="label">Transcripts</span>
              </div>
              <div class="stat">
                <span class="value">{{ formatNum(stats.segment_count) }}</span>
                <br><span class="label">Segments</span>
              </div>
              <div class="stat">
                <span class="value">{{ formatTime(stats.total_seconds) }}</span>
                <br><span class="label">Speaking time</span>
              </div>
              <div class="stat">
                <span class="value">{{ formatNum(stats.word_count) }}</span>
                <br><span class="label">Words</span>
              </div>
            </div>
          </template>
        </template>
      </Card>

      <Card v-if="statsByTranscript && statsByTranscript.length" class="by-transcript">
        <template #title>By transcript</template>
        <template #content>
          <div class="chart-section">
            <div class="chart-header">
              <label for="chart-stat-select" class="chart-label">Metric:</label>
              <Select
                id="chart-stat-select"
                v-model="chartStatKey"
                :options="chartMetricOptions"
                option-label="label"
                option-value="value"
                class="chart-select"
              />
            </div>
            <StatBarChart
              :labels="chartLabels"
              :values="chartValues"
              :y-axis-name="chartYAxisName"
              :value-formatter="chartValueFormatter"
            />
          </div>
          <ul class="transcript-list">
            <li v-for="row in statsByTranscript" :key="row.transcript_id" class="transcript-row">
              <div class="transcript-main">
                <span class="transcript-title">{{ row.transcript_title || 'Untitled' }}</span>
                <span class="transcript-stats">{{ formatTime(row.total_seconds) }}, {{ formatNum(row.segment_count) }} segments</span>
              </div>
              <div v-if="hasShareStats(row)" class="relative-share">
                <div v-if="row.share_speaking_time != null && row.share_speaking_time !== ''" class="share-bar">
                  <label>Share of speaking time</label>
                  <ProgressBar :value="(row.share_speaking_time ?? 0) * 100" :show-value="true" />
                </div>
                <div v-if="row.share_words != null && row.share_words !== ''" class="share-bar">
                  <label>Share of words</label>
                  <ProgressBar :value="(row.share_words ?? 0) * 100" :show-value="true" />
                </div>
              </div>
              <template v-if="statDefinitions.length">
                <div class="transcript-groups">
                  <div v-for="group in statDefinitions" :key="group.key" class="transcript-group">
                    <span class="group-mini-label">{{ group.label }}:</span>
                    <span class="group-values">
                      <template v-for="defn in group.stats" :key="defn.stat_key">
                        <span v-if="row[defn.stat_key] != null && row[defn.stat_key] !== ''" class="mini-stat">
                          {{ statLabel(defn.stat_key, defn.label, row[defn.stat_key]) }} {{ formatStatValue(defn.stat_key, row[defn.stat_key]) }}
                        </span>
                      </template>
                    </span>
                  </div>
                </div>
              </template>
            </li>
          </ul>
        </template>
      </Card>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Breadcrumb from 'primevue/breadcrumb'
import Card from 'primevue/card'
import Message from 'primevue/message'
import ProgressBar from 'primevue/progressbar'
import Select from 'primevue/select'
import StatBarChart from '../components/StatBarChart.vue'
import { formatDuration, formatDurationStatLabel } from '../utils/format.js'

const route = useRoute()
const router = useRouter()
const profile = ref(null)
const stats = ref({ transcript_count: 0, segment_count: 0, total_seconds: 0, word_count: 0 })
const statsByTranscript = ref([])
const statDefinitions = ref([])
const error = ref('')
const chartStatKey = ref('share_speaking_time')

const chartMetricOptions = [
  { label: 'Share of speaking time', value: 'share_speaking_time' },
  { label: 'Speaking time (min)', value: 'total_seconds' },
  { label: 'Word count', value: 'word_count' },
  { label: 'Share of words', value: 'share_words' },
]

const breadcrumbItems = computed(() => [
  {
    label: 'Dashboard',
    command: ({ originalEvent }) => {
      originalEvent?.preventDefault()
      router.push('/')
    },
  },
  { label: displayName.value || 'Speaker' },
])

const displayName = computed(() => {
  if (!profile.value) return ''
  const p = profile.value
  if (p.first_name && p.surname) return `${p.first_name} ${p.surname}`
  return p.display_name || ''
})

function hasShareStats(row) {
  return (row.share_speaking_time != null && row.share_speaking_time !== '') ||
    (row.share_words != null && row.share_words !== '')
}

function formatNum(n) {
  return Number(n).toLocaleString()
}

function formatTime(sec) {
  return formatDuration(sec)
}

function isDurationStat(statKey) {
  return statKey === 'total_seconds' || (typeof statKey === 'string' && statKey.endsWith('_sec'))
}

function statLabel(statKey, label, value) {
  if (isDurationStat(statKey) && (value != null && value !== '')) {
    return formatDurationStatLabel(label, value)
  }
  return label
}

function formatStatValue(statKey, value) {
  if (value == null || value === '') return '—'
  if (isDurationStat(statKey)) {
    return formatDuration(value)
  }
  if (statKey === 'share_speaking_time' || statKey === 'share_words') {
    return (Number(value) * 100).toFixed(1) + '%'
  }
  if (statKey === 'is_first_speaker' || statKey === 'is_last_speaker') {
    return value ? 'Yes' : 'No'
  }
  if (typeof value === 'number' && Number.isInteger(value)) return formatNum(value)
  if (typeof value === 'number') return value.toFixed(1)
  return String(value)
}

/** Truncate label for chart axis (max length in chars). */
function truncateLabel(str, maxLen = 32) {
  const s = String(str || '')
  if (s.length <= maxLen) return s
  return s.slice(0, maxLen - 1) + '…'
}

const chartLabels = computed(() =>
  (statsByTranscript.value || []).map((row) =>
    truncateLabel(row.transcript_title || 'Untitled')
  )
)

const chartValues = computed(() => {
  const key = chartStatKey.value
  return (statsByTranscript.value || []).map((row) => {
    const v = row[key]
    if (v == null || v === '') return 0
    if (key === 'share_speaking_time' || key === 'share_words') return Number(v) * 100
    if (key === 'total_seconds') return Number(v) / 60
    return Number(v)
  })
})

const chartYAxisName = computed(() => {
  const key = chartStatKey.value
  if (key === 'share_speaking_time' || key === 'share_words') return 'Share (%)'
  if (key === 'total_seconds') return 'Time (min)'
  return 'Count'
})

function chartValueFormatter(value) {
  const key = chartStatKey.value
  if (key === 'share_speaking_time' || key === 'share_words') {
    return Number(value).toFixed(1) + '%'
  }
  if (key === 'total_seconds') {
    return formatDuration(value * 60)
  }
  return formatNum(value)
}

onMounted(async () => {
  const id = route.params.idOrSlug
  if (!id) {
    error.value = 'No speaker ID.'
    return
  }
  try {
    const [defR, speakerR] = await Promise.all([
      fetch('/api/stat-definitions').then((r) => (r.ok ? r.json() : [])),
      fetch('/api/speakers/' + encodeURIComponent(id)),
    ])
    statDefinitions.value = Array.isArray(defR) ? defR : []
    if (speakerR.status === 404) throw new Error('Speaker not found')
    if (!speakerR.ok) throw new Error(speakerR.statusText)
    const data = await speakerR.json()
    profile.value = data.profile
    stats.value = data.stats
    statsByTranscript.value = data.stats_by_transcript || []
  } catch (e) {
    error.value = e.message
  }
})
</script>

<style scoped>
.mb-3 { margin-bottom: 1rem; }
.mb-4 { margin-bottom: 1.5rem; }
.stats {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 1rem;
  margin: 1rem 0;
}
.stat-group {
  margin-bottom: 1rem;
}
.stat-group .group-label {
  font-size: 0.9rem;
  font-weight: 600;
  margin: 0 0 0.5rem 0;
  color: var(--p-text-muted-color, #6b7280);
}
.stat {
  padding: 1rem;
  border-radius: 8px;
  background: var(--p-surface-0, #fff);
  border: 1px solid var(--p-surface-200, #e5e7eb);
  border-left: 3px solid var(--p-primary-500, #3b82f6);
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.04);
}
.stat .value {
  font-size: 1.75rem;
  font-weight: 700;
  line-height: 1.2;
  color: var(--p-text-color, #111);
}
.stat .label {
  font-size: 0.8rem;
  margin-top: 0.25rem;
  color: var(--p-text-muted-color, #6b7280);
  font-weight: 500;
}
.chart-section {
  margin-bottom: 1.5rem;
  padding: 1rem;
  border-radius: 8px;
  border: 1px solid var(--p-surface-200, #e5e7eb);
}
.chart-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}
.chart-label { font-size: 0.9rem; }
.chart-select { min-width: 200px; }
.transcript-list { list-style: none; padding: 0; margin: 0; }
.transcript-row {
  padding: 0.75rem 0;
  border-bottom: 1px solid var(--p-surface-200, #e5e7eb);
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.transcript-main { display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
.transcript-title { font-weight: 500; }
.transcript-stats { font-size: 0.9rem; opacity: 0.85; }
.relative-share { margin-top: 0.5rem; }
.share-bar { margin-bottom: 0.5rem; }
.share-bar label { display: block; font-size: 0.85rem; margin-bottom: 0.25rem; }
.transcript-groups { font-size: 0.85rem; padding-left: 0.5rem; margin-top: 0.25rem; }
.transcript-group { margin-top: 0.2rem; }
.group-mini-label { font-weight: 500; margin-right: 0.5rem; }
.group-values .mini-stat { margin-right: 1rem; }
</style>
