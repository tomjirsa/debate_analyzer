<template>
  <div>
    <p><router-link to="/admin/transcripts">← Transcripts</router-link></p>
    <h1>Speaker annotation</h1>
    <p v-if="transcript">{{ transcript.title || transcript.id }}</p>
    <p class="err">{{ err }}</p>

    <div v-if="!transcriptId" class="err">Missing transcript_id in URL.</div>
    <template v-else-if="transcript">
      <div class="section">
        <label>Video (optional – load from S3 or choose a local file)</label>
        <p :class="['video-status', videoS3Err ? 'err' : '']">{{ videoS3Status }}</p>
        <div style="margin-bottom: 0.5rem;">
          <input v-model="s3UriInput" type="text" placeholder="s3://bucket/key.mp4" style="width:100%;max-width:400px;margin-right:0.5rem;">
          <button type="button" @click="loadS3Video">Load video from S3</button>
        </div>
        <label style="margin-top:0.5rem;">Or load a local file</label>
        <input type="file" accept="video/mp4,video/webm,.mp4,.webm" @change="onVideoFile">
        <video
          ref="videoEl"
          controls
          style="display: none; width: 100%; max-height: 320px; background: #111; border-radius: 4px;"
          @timeupdate="updateCurrentSegment"
        />
      </div>

      <div class="section">
        <label>Transcript (click a line to jump to that time in the video)</label>
        <div ref="transcriptListEl" class="transcript">
          <div
            v-for="(seg, i) in segments"
            :key="i"
            :class="['segment', { current: currentSegmentIndex === i, highlight: highlightIndex === i }]"
            :data-start="seg.start"
            :data-end="seg.end"
            :data-speaker-id="seg.speaker_id_in_transcript"
            @click="seekTo(seg.start)"
          >
            <span class="time">{{ formatTime(seg.start) }} – {{ formatTime(seg.end) }}</span>
            <span class="speaker">{{ getDisplayName(seg.speaker_id_in_transcript) }}</span>
            {{ seg.text }}
          </div>
        </div>
      </div>

      <div class="section">
        <label>Assign each speaker ID to a profile (or create new)</label>
        <div v-for="m in mappingRows" :key="m.speaker_id_in_transcript" class="mapping">
          <label @click="scrollToSegment(m.speaker_id_in_transcript)">{{ m.speaker_id_in_transcript }}</label>
          <select :value="mappingBySpeaker[m.speaker_id_in_transcript] || ''" @change="onMappingChange(m.speaker_id_in_transcript, $event)">
            <option value="">-- Unassigned --</option>
            <option v-for="s in speakers" :key="s.id" :value="s.id">{{ displayName(s) }}</option>
            <option value="__new__">+ Create new profile</option>
          </select>
        </div>
        <div v-if="showNewSpeaker" id="newSpeaker" class="new-speaker">
          <input v-model="newFirstName" type="text" placeholder="First name">
          <input v-model="newSurname" type="text" placeholder="Surname">
          <input v-model="newSlug" type="text" placeholder="Slug (optional)">
          <input v-model="newShortDescription" type="text" placeholder="Short description (optional)" style="min-width: 200px;">
          <button type="button" @click="createAndAssign">Create and assign</button>
        </div>
        <button type="button" @click="saveMappings">Save mappings</button>
        <span :class="saveStatusClass">{{ saveStatus }}</span>
      </div>

      <div v-if="speakerStats.length && statDefinitions.length" class="section speaker-stats-section">
        <label>Speaker statistics</label>
        <div v-for="s in speakerStats" :key="s.speaker_id_in_transcript" class="speaker-stat-card">
          <h4 class="speaker-stat-id">{{ s.speaker_id_in_transcript }}</h4>
          <div v-for="group in statDefinitions" :key="group.key" class="speaker-stat-group">
            <span class="group-label">{{ group.label }}</span>
            <ul class="stat-list">
              <li v-for="defn in group.stats" :key="defn.stat_key" class="stat-line">
                <span class="stat-label">{{ statLabel(defn.stat_key, defn.label, s[defn.stat_key]) }}</span>
                <span class="stat-value">{{ formatStatValue(defn.stat_key, s[defn.stat_key]) }}</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAdminAuth } from '../composables/useAdminAuth'
import { formatDuration, formatDurationStatLabel } from '../utils/format.js'

const route = useRoute()
const { apiFetch } = useAdminAuth()

const transcriptId = computed(() => route.query.transcript_id || '')

const transcript = ref(null)
const segments = ref([])
const mappings = ref([])
const speakerStats = ref([])
const statDefinitions = ref([])
const speakers = ref([])
const err = ref('')

const videoEl = ref(null)
const transcriptListEl = ref(null)
const s3UriInput = ref('')
const videoS3Status = ref('')
const videoS3Err = ref(false)
const currentSegmentIndex = ref(-1)
const highlightIndex = ref(-1)

const showNewSpeaker = ref(false)
const creatingForSpeakerId = ref(null)
const newFirstName = ref('')
const newSurname = ref('')
const newSlug = ref('')
const newShortDescription = ref('')

const saveStatus = ref('')
const saveStatusClass = computed(() => (saveStatus.value === 'Saved.' ? 'ok' : saveStatus.value ? 'err' : ''))

const mappingBySpeaker = computed(() => {
  const out = {}
  mappings.value.forEach((m) => {
    if (m.speaker_profile_id) out[m.speaker_id_in_transcript] = m.speaker_profile_id
  })
  return out
})

const mappingRows = computed(() => {
  const byId = {}
  segments.value.forEach((s) => {
    const id = s.speaker_id_in_transcript
    if (id && !byId[id]) byId[id] = { speaker_id_in_transcript: id }
  })
  return Object.values(byId)
})

function displayName(p) {
  return (p.first_name && p.surname) ? `${p.first_name} ${p.surname}` : (p.display_name || p.id)
}

function getDisplayName(speakerIdInTranscript) {
  const profileId = mappingBySpeaker.value[speakerIdInTranscript]
  const profile = speakers.value.find((s) => s.id === profileId)
  return profile ? displayName(profile) : speakerIdInTranscript
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
  if (typeof value === 'number' && Number.isInteger(value)) return String(value)
  if (typeof value === 'number') return value.toFixed(1)
  return String(value)
}

function load() {
  if (!transcriptId.value) return
  err.value = ''
  Promise.all([
    apiFetch('/api/admin/transcripts/' + transcriptId.value).then((r) => {
      if (r.status === 401) return Promise.reject(new Error('Unauthorized'))
      return r.ok ? r.json() : Promise.reject(new Error(r.statusText))
    }),
    apiFetch('/api/admin/speakers').then((r) => {
      if (r.status === 401) return Promise.reject(new Error('Unauthorized'))
      return r.ok ? r.json() : Promise.reject(new Error(r.statusText))
    }),
    fetch('/api/stat-definitions').then((r) => (r.ok ? r.json() : [])),
  ])
    .then(([data, speakerList, defs]) => {
      transcript.value = data.transcript
      mappings.value = data.mappings || []
      speakerStats.value = data.speaker_stats || []
      statDefinitions.value = Array.isArray(defs) ? defs : []
      speakers.value = speakerList || []
      segments.value = data.segments || []
      if (transcript.value.video_path && transcript.value.video_path.trim().startsWith('s3://')) {
        s3UriInput.value = transcript.value.video_path
      }
      tryAutoLoadVideo()
    })
    .catch((e) => {
      if (e.message === 'Unauthorized') {
        err.value = 'Authentication required. Log in on the admin page first.'
      } else {
        err.value = e.message
      }
    })
}

function deriveVideoUri(sourceUri) {
  if (!sourceUri || !sourceUri.startsWith('s3://')) return null
  let u = sourceUri.replace(/\/transcripts\//g, '/videos/')
  if (u.endsWith('_transcription.json')) u = u.slice(0, -'_transcription.json'.length) + '.mp4'
  else if (u.endsWith('.json')) u = u.slice(0, -5) + '.mp4'
  return u
}

function setVideoFromUrl(url) {
  if (!videoEl.value) return
  if (videoEl.value.src && videoEl.value.src.startsWith('blob:')) URL.revokeObjectURL(videoEl.value.src)
  videoEl.value.src = url
  videoEl.value.style.display = 'block'
}

function tryAutoLoadVideo() {
  if (!transcript.value || !transcript.value.source_uri?.startsWith('s3://')) return
  const derived = deriveVideoUri(transcript.value.source_uri)
  if (!derived) return
  videoS3Status.value = 'Loading video from S3…'
  videoS3Err.value = false
  apiFetch('/api/admin/transcripts/' + transcriptId.value + '/video-url?s3_uri=' + encodeURIComponent(derived))
    .then((r) => (r.ok ? r.json() : r.json().then((j) => Promise.reject(new Error(j.detail || r.statusText)))))
    .then((data) => {
      setVideoFromUrl(data.url)
      videoS3Status.value = ''
    })
    .catch(() => {
      videoS3Status.value = 'S3 video not found. Use local file or enter S3 URI below.'
      videoS3Err.value = true
    })
}

function loadS3Video() {
  const uri = s3UriInput.value?.trim() || (transcript.value?.video_path?.trim().startsWith('s3://') ? transcript.value.video_path.trim() : '')
  if (!uri) {
    videoS3Status.value = 'Enter an S3 URI (e.g. s3://bucket/key.mp4) or use transcript video_path.'
    videoS3Err.value = true
    return
  }
  videoS3Status.value = 'Loading…'
  videoS3Err.value = false
  apiFetch('/api/admin/transcripts/' + transcriptId.value + '/video-url?s3_uri=' + encodeURIComponent(uri))
    .then((r) => (r.ok ? r.json() : r.json().then((j) => Promise.reject(new Error(j.detail || r.statusText)))))
    .then((data) => {
      setVideoFromUrl(data.url)
      videoS3Status.value = ''
    })
    .catch((e) => {
      videoS3Status.value = e.message || 'Failed to load video from S3.'
      videoS3Err.value = true
    })
}

function onVideoFile(ev) {
  const file = ev.target.files?.[0]
  if (!file || !videoEl.value) return
  if (videoEl.value.src?.startsWith('blob:')) URL.revokeObjectURL(videoEl.value.src)
  videoEl.value.src = URL.createObjectURL(file)
  videoEl.value.style.display = 'block'
  videoS3Status.value = ''
}

function updateCurrentSegment() {
  if (!videoEl.value?.src || !segments.value.length) return
  const t = videoEl.value.currentTime
  let idx = -1
  segments.value.forEach((seg, i) => {
    if (t >= seg.start && t < seg.end) idx = i
  })
  currentSegmentIndex.value = idx
}

function seekTo(start) {
  if (videoEl.value?.src) {
    videoEl.value.currentTime = start
    videoEl.value.play()
  }
}

function scrollToSegment(speakerId) {
  const first = transcriptListEl.value?.querySelector(`.segment[data-speaker-id="${speakerId}"]`)
  if (first) {
    first.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    highlightIndex.value = segments.value.findIndex((s) => s.speaker_id_in_transcript === speakerId)
    setTimeout(() => { highlightIndex.value = -1 }, 1500)
  }
}

function onMappingChange(speakerId, ev) {
  const val = ev.target.value
  if (val === '__new__') {
    creatingForSpeakerId.value = speakerId
    showNewSpeaker.value = true
  } else {
    const existing = mappings.value.find((m) => m.speaker_id_in_transcript === speakerId)
    if (existing) {
      existing.speaker_profile_id = val || null
    } else {
      mappings.value.push({ speaker_id_in_transcript: speakerId, speaker_profile_id: val || null })
    }
  }
}

function createAndAssign() {
  const first = newFirstName.value.trim()
  const last = newSurname.value.trim()
  if (!first || !last) return
  apiFetch('/api/admin/speakers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      first_name: first,
      surname: last,
      slug: newSlug.value.trim() || null,
      short_description: newShortDescription.value.trim() || null,
    }),
  })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.statusText))))
    .then((profile) => {
      speakers.value.push(profile)
      if (creatingForSpeakerId.value) {
        const m = mappings.value.find((x) => x.speaker_id_in_transcript === creatingForSpeakerId.value)
        if (m) m.speaker_profile_id = profile.id
        else mappings.value.push({ speaker_id_in_transcript: creatingForSpeakerId.value, speaker_profile_id: profile.id })
      }
      showNewSpeaker.value = false
      newFirstName.value = ''
      newSurname.value = ''
      newSlug.value = ''
      newShortDescription.value = ''
      creatingForSpeakerId.value = null
    })
    .catch((e) => { saveStatus.value = e.message })
}

function buildMappingsBody() {
  const body = {}
  mappingRows.value.forEach((row) => {
    const profileId = mappingBySpeaker.value[row.speaker_id_in_transcript]
    body[row.speaker_id_in_transcript] = (profileId && profileId !== '__new__') ? profileId : null
  })
  return body
}

function saveMappings() {
  const body = buildMappingsBody()
  saveStatus.value = 'Saving...'
  apiFetch('/api/admin/transcripts/' + transcriptId.value + '/mappings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mappings: body }),
  })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.statusText))))
    .then(() => {
      saveStatus.value = 'Saved.'
    })
    .catch((e) => {
      saveStatus.value = e.message
    })
}

onMounted(load)
watch(transcriptId, () => { if (transcriptId.value) load() })
</script>

<style scoped>
.section { margin-bottom: 1.5rem; }
.mapping { display: flex; align-items: center; gap: 0.75rem; margin: 0.5rem 0; flex-wrap: wrap; }
.mapping label { margin: 0; font-weight: normal; min-width: 100px; cursor: pointer; }
.mapping label:hover { text-decoration: underline; }
.transcript { max-height: 360px; overflow-y: auto; border: 1px solid #ccc; border-radius: 4px; padding: 0.5rem; }
.segment { padding: 0.35rem 0.5rem; margin: 2px 0; border-radius: 4px; cursor: pointer; }
.segment:hover { background: #f0f0f0; }
.segment.current { background: #e0e8ff; }
.segment.highlight { background: #fff3cd; }
.segment .time { font-size: 0.85em; color: #666; margin-right: 0.5rem; }
.segment .speaker { font-weight: 600; margin-right: 0.5rem; color: #333; }
.new-speaker { margin-top: 0.5rem; padding: 0.5rem; background: #f0f8ff; border-radius: 4px; }
.new-speaker input { margin-right: 0.5rem; }
select { min-width: 200px; }
.speaker-stats-section { margin-top: 1rem; }
.speaker-stat-card {
  border: 1px solid #ddd;
  border-radius: 6px;
  padding: 1rem;
  margin-bottom: 1rem;
  background: #fafafa;
}
.speaker-stat-id { margin: 0 0 0.5rem 0; font-size: 1rem; }
.speaker-stat-group { margin-top: 0.75rem; }
.speaker-stat-group .group-label { font-weight: 600; font-size: 0.9rem; }
.stat-list { list-style: none; padding: 0; margin: 0.25rem 0 0 0.5rem; }
.stat-line { display: flex; justify-content: space-between; gap: 1rem; padding: 0.2rem 0; font-size: 0.9rem; }
.stat-label { color: #555; }
.stat-value { font-weight: 500; }
</style>
