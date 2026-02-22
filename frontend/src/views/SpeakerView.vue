<template>
  <div>
    <p><router-link to="/">← Dashboard</router-link></p>
    <div v-if="error" class="err">{{ error }}</div>
    <div v-else-if="profile">
      <h1>{{ displayName }}</h1>
      <p v-if="profile.short_description" class="short-desc">{{ profile.short_description }}</p>
      <p v-if="profile.bio">{{ profile.bio }}</p>
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
      <section v-if="statsByTranscript && statsByTranscript.length" class="by-transcript">
        <h2>By transcript</h2>
        <div class="chart-section">
          <div class="chart-header">
            <label for="chart-stat-select">Metric:</label>
            <select id="chart-stat-select" v-model="chartStatKey" class="chart-select">
              <option value="share_speaking_time">Share of speaking time</option>
              <option value="total_seconds">Speaking time (min)</option>
              <option value="word_count">Word count</option>
              <option value="share_words">Share of words</option>
            </select>
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
              <h4 class="relative-share-title">Relative share</h4>
              <div class="relative-share-gauges">
                <ShareGauge
                  v-if="row.share_speaking_time != null && row.share_speaking_time !== ''"
                  :value="row.share_speaking_time"
                  label="Share of speaking time"
                />
                <ShareGauge
                  v-if="row.share_words != null && row.share_words !== ''"
                  :value="row.share_words"
                  label="Share of words"
                />
              </div>
            </div>
            <template v-if="statDefinitions.length">
              <div class="transcript-groups">
                <div v-for="group in statDefinitions" :key="group.key" class="transcript-group">
                  <span class="group-mini-label">{{ group.label }}:</span>
                  <span class="group-values">
                    <template v-for="defn in group.stats" :key="defn.stat_key">
                      <span v-if="!isShareStat(defn.stat_key) && row[defn.stat_key] != null && row[defn.stat_key] !== ''" class="mini-stat">
                        {{ statLabel(defn.stat_key, defn.label, row[defn.stat_key]) }} {{ formatStatValue(defn.stat_key, row[defn.stat_key]) }}
                      </span>
                    </template>
                  </span>
                </div>
              </div>
            </template>
          </li>
        </ul>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import StatBarChart from '../components/StatBarChart.vue'
import ShareGauge from '../components/ShareGauge.vue'
import { formatDuration, formatDurationStatLabel } from '../utils/format.js'

const route = useRoute()
const profile = ref(null)
const stats = ref({ transcript_count: 0, segment_count: 0, total_seconds: 0, word_count: 0 })
const statsByTranscript = ref([])
const statDefinitions = ref([])
const error = ref('')
const chartStatKey = ref('share_speaking_time')

const displayName = computed(() => {
  if (!profile.value) return ''
  const p = profile.value
  if (p.first_name && p.surname) return `${p.first_name} ${p.surname}`
  return p.display_name || ''
})

function formatNum(n) {
  return Number(n).toLocaleString()
}

function formatTime(sec) {
  return formatDuration(sec)
}

function hasShareStats(row) {
  return (
    (row.share_speaking_time != null && row.share_speaking_time !== '') ||
    (row.share_words != null && row.share_words !== '')
  )
}

function isShareStat(statKey) {
  return statKey === 'share_speaking_time' || statKey === 'share_words'
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
.stats {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 1rem;
  margin: 1rem 0;
}
.stat-group {
  margin-bottom: 1.5rem;
}
.stat-group .group-label {
  font-size: 1rem;
  margin: 0 0 0.5rem 0;
  color: #444;
}
.stat {
  background: #f5f5f5;
  padding: 0.75rem;
  border-radius: 6px;
}
.stat .value { font-size: 1.25rem; font-weight: 600; }
.stat .label { font-size: 0.85rem; color: #666; }
.by-transcript { margin-top: 1.5rem; }
.by-transcript h2 { font-size: 1.1rem; margin-bottom: 0.5rem; }
.chart-section {
  margin-bottom: 1.5rem;
  padding: 1rem;
  background: #fafafa;
  border-radius: 8px;
  border: 1px solid #eee;
}
.chart-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}
.chart-header label { font-size: 0.9rem; color: #555; }
.chart-select {
  padding: 0.35rem 0.5rem;
  font-size: 0.9rem;
  border: 1px solid #ccc;
  border-radius: 4px;
}
.transcript-list { list-style: none; padding: 0; margin: 0; }
.transcript-row {
  padding: 0.5rem 0;
  border-bottom: 1px solid #eee;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.transcript-main { display: flex; justify-content: space-between; gap: 1rem; }
.transcript-title { font-weight: 500; }
.transcript-stats { color: #666; font-size: 0.9rem; }
.relative-share {
  margin: 0.5rem 0;
  padding: 0.5rem 0;
  border-top: 1px solid #eee;
}
.relative-share-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: #444;
  margin: 0 0 0.5rem 0;
}
.relative-share-gauges {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
  align-items: flex-start;
}
.transcript-groups { font-size: 0.85rem; color: #555; padding-left: 0.5rem; }
.transcript-group { margin-top: 0.2rem; }
.group-mini-label { font-weight: 500; margin-right: 0.5rem; }
.group-values .mini-stat { margin-right: 1rem; }
</style>
