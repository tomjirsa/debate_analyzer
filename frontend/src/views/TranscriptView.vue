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
          <MetricStatGrid :items="summaryStatsItems" />
        </template>
      </Card>

      <Card
        v-if="
          llmAnalysis &&
          llmAnalysis.transcript_summary &&
          llmAnalysis.transcript_summary.summary
        "
        class="mb-4"
      >
        <template #title>Transcript summary</template>
        <template #content>
          <p class="contribution-summary">
            {{ llmAnalysis.transcript_summary.summary }}
          </p>
          <div
            v-if="
              llmAnalysis.transcript_summary.keywords &&
              llmAnalysis.transcript_summary.keywords.length
            "
            class="contribution-keywords"
          >
            <KeywordTag
              v-for="kw in llmAnalysis.transcript_summary.keywords"
              :key="kw"
              :text="kw"
            />
          </div>
        </template>
      </Card>

      <Card
        v-if="llmAnalysis && llmAnalysis.speaker_contributions && llmAnalysis.speaker_contributions.length"
        class="mb-4"
      >
        <template #title>Speaker contributions</template>
        <template #content>
          <div
            v-for="group in contributionsBySpeaker"
            :key="group.speakerId"
            class="speaker-contributions-group"
          >
            <h3 class="speaker-contributions-heading">
              {{ speakerDisplayName(group.speakerId) }}
            </h3>
            <ul class="contributions-list">
              <li
                v-for="c in group.contributions"
                :key="c.id"
                class="contribution-item"
              >
                <span v-if="c.id" class="contribution-id">{{ c.id }}</span>
                <p class="contribution-summary">{{ c.summary }}</p>
                <div v-if="c.keywords && c.keywords.length" class="contribution-keywords">
                  <KeywordTag
                    v-for="kw in c.keywords"
                    :key="kw"
                    :text="kw"
                  />
                </div>
              </li>
            </ul>
          </div>
        </template>
      </Card>

      <Card v-if="speakerStats && speakerStats.length" class="by-speaker">
        <template #title>By speaker</template>
        <template #content>
          <ChartCard>
            <template #controls>
              <label for="chart-stat-select" class="chart-label">Metric:</label>
              <Select
                id="chart-stat-select"
                v-model="chartStatKey"
                :options="chartMetricOptions"
                option-label="label"
                option-value="value"
                class="chart-select"
              />
            </template>
            <StatBarChart
              :labels="chartLabels"
              :values="chartValues"
              :y-axis-name="chartYAxisName"
              :value-formatter="chartValueFormatter"
            />
          </ChartCard>
          <DataTable
            :value="speakerStats"
            data-key="speaker_id_in_transcript"
            sort-mode="single"
            removable-sort
            class="speaker-stats-table"
          >
            <Column field="speaker_display_name" header="Speaker" sortable>
              <template #body="{ data }">
                {{ data.speaker_display_name || data.speaker_id_in_transcript }}
              </template>
            </Column>
            <Column field="share_speaking_time" header="Share of speaking time" sortable>
              <template #body="{ data }">
                {{ formatShare(data.share_speaking_time) }}
              </template>
            </Column>
            <Column field="share_words" header="Share of words" sortable>
              <template #body="{ data }">
                {{ formatShare(data.share_words) }}
              </template>
            </Column>
            <Column field="total_seconds" header="Speaking time" sortable>
              <template #body="{ data }">
                {{ formatTime(data.total_seconds) }}
              </template>
            </Column>
            <Column field="word_count" header="Words" sortable>
              <template #body="{ data }">
                {{ formatNum(data.word_count) }}
              </template>
            </Column>
            <Column field="segment_count" header="Segments" sortable>
              <template #body="{ data }">
                {{ formatNum(data.segment_count) }}
              </template>
            </Column>
            <Column field="wpm" header="WPM" sortable>
              <template #body="{ data }">
                {{ formatNum(data.wpm) }}
              </template>
            </Column>
            <Column field="turn_count" header="Turns" sortable>
              <template #body="{ data }">
                {{ formatNum(data.turn_count) }}
              </template>
            </Column>
          </DataTable>
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
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Message from 'primevue/message'
import Select from 'primevue/select'
import MetricStatGrid from '../components/MetricStatGrid.vue'
import ChartCard from '../components/ChartCard.vue'
import KeywordTag from '../components/KeywordTag.vue'
import StatBarChart from '../components/StatBarChart.vue'
import { formatDuration } from '../utils/format.js'

const route = useRoute()
const groupIdOrSlug = computed(() => route.params.groupId)
const transcriptId = computed(() => route.params.transcriptId)

const transcript = ref(null)
const speakerStats = ref([])
const llmAnalysis = ref(null)
const groupName = ref('')
const error = ref('')
const chartStatKey = ref('share_speaking_time')

/** Map speaker_id_in_transcript -> speaker_display_name for contribution labels. */
const speakerDisplayNameMap = computed(() => {
  const map = {}
  for (const row of speakerStats.value || []) {
    const id = row.speaker_id_in_transcript
    if (id != null && id !== '') {
      map[id] = row.speaker_display_name || id
    }
  }
  return map
})

function speakerDisplayName(speakerId) {
  if (speakerId == null || speakerId === '') return '—'
  return speakerDisplayNameMap.value[speakerId] ?? speakerId
}

/** Group speaker_contributions by speaker_id_in_transcript. */
const contributionsBySpeaker = computed(() => {
  const list = llmAnalysis.value?.speaker_contributions || []
  const bySpeaker = new Map()
  for (const c of list) {
    const sid = c.speaker_id_in_transcript ?? ''
    if (!bySpeaker.has(sid)) {
      bySpeaker.set(sid, [])
    }
    bySpeaker.get(sid).push(c)
  }
  return Array.from(bySpeaker.entries()).map(([speakerId, contributions]) => ({
    speakerId,
    contributions,
  }))
})

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

const summaryStatsItems = computed(() => [
  { key: 'duration', value: formatTime(transcript.value?.duration), label: 'Duration' },
  { key: 'words', value: formatNum(transcript.value?.stats_total_words), label: 'Words' },
  { key: 'segments', value: formatNum(transcript.value?.stats_segment_count), label: 'Segments' },
  { key: 'speakers', value: formatNum(transcript.value?.speakers_count), label: 'Speakers' },
])

function formatShare(value) {
  if (value == null || value === '') return '—'
  const num = Number(value)
  if (Number.isNaN(num)) return '—'
  return (num * 100).toFixed(1) + '%'
}

function truncateLabel(str, maxLen = 20) {
  const s = String(str || '')
  if (s.length <= maxLen) return s
  return s.slice(0, maxLen - 1) + '…'
}

const chartLabels = computed(() =>
  (speakerStats.value || []).map((row) =>
    truncateLabel(row.speaker_display_name || row.speaker_id_in_transcript)
  )
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
    llmAnalysis.value = data.llm_analysis || null
  } catch (e) {
    error.value = e.message
    transcript.value = null
    speakerStats.value = []
    llmAnalysis.value = null
  }
}

onMounted(load)
watch([groupIdOrSlug, transcriptId], load)
</script>

<style scoped>
.mb-3 { margin-bottom: 1rem; }
.mb-4 { margin-bottom: 1.5rem; }
.speaker-stats-table { margin-top: 1rem; }

.speaker-contributions-group {
  margin-bottom: 1.5rem;
}
.speaker-contributions-group:last-child {
  margin-bottom: 0;
}
.speaker-contributions-heading {
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 0.5rem;
  color: var(--p-text-color, #111);
}
.contributions-list {
  margin: 0;
  padding-left: 1.25rem;
  list-style: disc;
}
.contribution-item {
  margin-bottom: 0.75rem;
  line-height: 1.4;
}
.contribution-id {
  font-size: 0.8rem;
  color: var(--p-text-muted-color, #6b7280);
  margin-right: 0.5rem;
}
.contribution-summary {
  margin: 0.25rem 0;
  font-size: 0.95rem;
}
.contribution-keywords {
  margin-top: 0.25rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}
</style>
