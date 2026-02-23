<template>
  <div>
    <Breadcrumb :model="breadcrumbItems" class="mb-3">
      <template #item="{ item }">
        <router-link v-if="item.to" :to="item.to" class="p-menuitem-link">{{ item.label }}</router-link>
        <span v-else>{{ item.label }}</span>
      </template>
    </Breadcrumb>

    <Message v-if="error" severity="error">{{ error }}</Message>

    <template v-else-if="transcript">
      <Card class="mb-4">
        <template #title>{{ transcriptTitle }}</template>
        <template #subtitle>{{ transcriptSubtitle }}</template>
        <template #content />
      </Card>

      <Card class="mb-4">
        <template #title>Summary</template>
        <template #content>
          <div class="stats">
            <div class="stat">
              <span class="value">{{ formatTime(transcript.duration) }}</span>
              <br><span class="label">Duration</span>
            </div>
            <div class="stat">
              <span class="value">{{ formatNum(transcript.stats_total_words) }}</span>
              <br><span class="label">Words</span>
            </div>
            <div class="stat">
              <span class="value">{{ formatNum(transcript.stats_segment_count) }}</span>
              <br><span class="label">Segments</span>
            </div>
            <div class="stat">
              <span class="value">{{ formatNum(transcript.speakers_count) }}</span>
              <br><span class="label">Speakers</span>
            </div>
          </div>
        </template>
      </Card>

      <Card v-if="speakerStats && speakerStats.length" class="by-speaker">
        <template #title>By speaker</template>
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
          <ul class="speaker-list">
            <li v-for="row in speakerStats" :key="row.speaker_id_in_transcript" class="speaker-row">
              <div class="speaker-main">
                <span class="speaker-id">{{ row.speaker_id_in_transcript }}</span>
                <span class="speaker-stats">{{ formatTime(row.total_seconds) }}, {{ formatNum(row.word_count) }} words</span>
              </div>
              <div v-if="hasShareStats(row)" class="relative-share">
                <div v-if="row.share_speaking_time != null" class="share-bar">
                  <label>Share of speaking time</label>
                  <ProgressBar :value="(row.share_speaking_time ?? 0) * 100" :show-value="true" />
                </div>
                <div v-if="row.share_words != null" class="share-bar">
                  <label>Share of words</label>
                  <ProgressBar :value="(row.share_words ?? 0) * 100" :show-value="true" />
                </div>
              </div>
            </li>
          </ul>
        </template>
      </Card>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import Breadcrumb from 'primevue/breadcrumb'
import Card from 'primevue/card'
import Message from 'primevue/message'
import ProgressBar from 'primevue/progressbar'
import Select from 'primevue/select'
import StatBarChart from '../components/StatBarChart.vue'
import { formatDuration } from '../utils/format.js'

const route = useRoute()
const groupIdOrSlug = computed(() => route.params.groupId)
const transcriptId = computed(() => route.params.transcriptId)

const transcript = ref(null)
const speakerStats = ref([])
const groupName = ref('')
const error = ref('')
const chartStatKey = ref('share_speaking_time')

const chartMetricOptions = [
  { label: 'Share of speaking time', value: 'share_speaking_time' },
  { label: 'Speaking time (min)', value: 'total_seconds' },
  { label: 'Word count', value: 'word_count' },
  { label: 'Share of words', value: 'share_words' },
]

const transcriptTitle = computed(() => {
  const t = transcript.value
  if (!t) return ''
  return t.title || t.source_uri?.split('/').pop()?.replace('_transcription.json', '') || t.id
})

const transcriptSubtitle = computed(() => {
  const t = transcript.value
  if (!t) return ''
  const parts = []
  if (t.duration != null) parts.push(formatDuration(t.duration))
  if (t.stats_total_words != null) parts.push(formatNum(t.stats_total_words) + ' words')
  if (t.stats_segment_count != null) parts.push(formatNum(t.stats_segment_count) + ' segments')
  return parts.join(' · ') || ''
})

const breadcrumbItems = computed(() => {
  const items = [{ label: 'Dashboards', to: '/' }]
  if (groupName.value && groupIdOrSlug.value) {
    items.push({ label: groupName.value, to: '/group/' + encodeURIComponent(groupIdOrSlug.value) })
  }
  if (transcript.value) {
    items.push({ label: transcriptTitle.value })
  }
  return items
})

function formatNum(n) {
  if (n == null || n === '') return '—'
  const num = Number(n)
  if (Number.isNaN(num)) return '—'
  return num.toLocaleString()
}

function formatTime(sec) {
  if (sec == null && sec !== 0) return '—'
  return formatDuration(sec)
}

function hasShareStats(row) {
  return (row.share_speaking_time != null && row.share_speaking_time !== '') ||
    (row.share_words != null && row.share_words !== '')
}

function truncateLabel(str, maxLen = 20) {
  const s = String(str || '')
  if (s.length <= maxLen) return s
  return s.slice(0, maxLen - 1) + '…'
}

const chartLabels = computed(() =>
  (speakerStats.value || []).map((row) => truncateLabel(row.speaker_id_in_transcript))
)

const chartValues = computed(() => {
  const key = chartStatKey.value
  return (speakerStats.value || []).map((row) => {
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

async function load() {
  const gid = groupIdOrSlug.value
  const tid = transcriptId.value
  if (!gid || !tid) {
    error.value = 'Missing group or transcript.'
    return
  }
  error.value = ''
  try {
    const groupRes = await fetch('/api/groups/' + encodeURIComponent(gid))
    if (groupRes.ok) {
      const g = await groupRes.json()
      groupName.value = g.name || ''
    }
    const res = await fetch(
      '/api/groups/' + encodeURIComponent(gid) + '/transcripts/' + encodeURIComponent(tid)
    )
    if (res.status === 404) throw new Error('Transcript not found')
    if (!res.ok) throw new Error(res.statusText)
    const data = await res.json()
    transcript.value = data.transcript
    speakerStats.value = data.speaker_stats || []
  } catch (e) {
    error.value = e.message
    transcript.value = null
    speakerStats.value = []
  }
}

onMounted(load)
watch([groupIdOrSlug, transcriptId], load)
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
.speaker-list { list-style: none; padding: 0; margin: 0; }
.speaker-row {
  padding: 0.75rem 0;
  border-bottom: 1px solid var(--p-surface-200, #e5e7eb);
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.speaker-main { display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
.speaker-id { font-weight: 500; }
.speaker-stats { font-size: 0.9rem; opacity: 0.85; }
.relative-share { margin-top: 0.5rem; }
.share-bar { margin-bottom: 0.5rem; }
.share-bar label { display: block; font-size: 0.85rem; margin-bottom: 0.25rem; }
</style>
