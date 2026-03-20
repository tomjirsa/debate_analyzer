<template>
  <div>
    <p class="mb-3">
      <router-link to="/admin/transcripts">← Transcripts</router-link>
    </p>
    <h2 class="mt-0">Speaker annotation</h2>
    <p v-if="transcript">{{ transcript.title || transcript.id }}</p>

    <Message v-if="err" severity="error">{{ err }}</Message>

    <div v-if="!transcriptId" class="mb-3">
      <Message severity="error">Missing transcript_id in URL.</Message>
    </div>

    <template v-else-if="transcript">
      <DashboardCard class="mb-4">
        <template #title>Video</template>
        <template #subtitle>Optional – load from S3 or choose a local file</template>
        <template #content>
          <Message v-if="videoS3Err" severity="warn">{{ videoS3Status }}</Message>
          <p v-else-if="videoS3Status" class="video-status">{{ videoS3Status }}</p>
          <div class="flex flex-wrap align-items-center gap-2 mb-2">
            <InputText
              v-model="s3UriInput"
              placeholder="s3://bucket/key.mp4"
              class="flex-1"
              style="min-width: 200px; max-width: 400px;"
            />
            <Button label="Load video from S3" @click="loadS3Video" />
          </div>
          <label class="block mb-1">Or load a local file</label>
          <input type="file" accept="video/mp4,video/webm,.mp4,.webm" @change="onVideoFile" class="mb-2" />
          <video
            ref="videoEl"
            controls
            class="video-player"
            style="display: none; width: 100%; max-height: 320px; background: var(--p-surface-900, #111); border-radius: var(--p-border-radius, 6px);"
            @timeupdate="updateCurrentSegment"
          />
        </template>
      </DashboardCard>

      <DashboardCard class="mb-4">
        <template #title>Transcript</template>
        <template #subtitle>Click a line to jump to that time in the video</template>
        <template #content>
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
        </template>
      </DashboardCard>

      <DashboardCard class="mb-4">
        <template #title>Assign speaker IDs</template>
        <template #subtitle>Assign each speaker ID to a profile (or create new)</template>
        <template #content>
          <div v-for="m in mappingRows" :key="m.speaker_id_in_transcript" class="mapping">
            <label class="mapping-label" @click="scrollToSegment(m.speaker_id_in_transcript)">{{ m.speaker_id_in_transcript }}</label>
            <Select
              :model-value="mappingBySpeaker[m.speaker_id_in_transcript] || ''"
              :options="speakerSelectOptions"
              option-label="label"
              option-value="value"
              class="mapping-select"
              @update:model-value="(val) => onMappingChangeValue(m.speaker_id_in_transcript, val)"
            />
          </div>
          <Panel v-if="showNewSpeaker" header="Create new profile" class="mt-2">
            <div class="flex flex-column gap-2 w-full">
              <div class="flex flex-column gap-1 w-full">
                <label>First name</label>
                <InputText v-model="newFirstName" placeholder="First name" class="w-full" />
              </div>
              <div class="flex flex-column gap-1 w-full">
                <label>Surname</label>
                <InputText v-model="newSurname" placeholder="Surname" class="w-full" />
              </div>
              <div class="flex flex-column gap-1 w-full">
                <label>Slug (optional)</label>
                <InputText v-model="newSlug" placeholder="Slug" class="w-full" />
              </div>
              <div class="flex flex-column gap-1 w-full">
                <label>Short description (optional)</label>
                <InputText v-model="newShortDescription" placeholder="Short description" class="w-full" />
              </div>
              <Button label="Create and assign" @click="createAndAssign" />
            </div>
          </Panel>
          <div class="flex align-items-center gap-2 mt-2">
            <Button label="Save mappings" @click="saveMappings" />
            <Message v-if="saveStatus" :severity="saveStatus === 'Saved.' ? 'success' : 'error'">{{ saveStatus }}</Message>
          </div>
        </template>
      </DashboardCard>

      <DashboardCard v-if="speakerStats.length && statDefinitions.length">
        <template #title>Speaker statistics</template>
        <template #content>
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
        </template>
      </DashboardCard>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Panel from 'primevue/panel'
import Select from 'primevue/select'
import DashboardCard from '../components/DashboardCard.vue'
import { useAdminAuth } from '../composables/useAdminAuth'
import { formatDuration, formatDurationStatLabel } from '../utils/format.js'

const route = useRoute()
const router = useRouter()
const { clearAuth, apiFetch } = useAdminAuth()

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

const mappingBySpeaker = computed(() => {
  const out = {}
  mappings.value.forEach((m) => {
    if (m.speaker_profile_id) out[m.speaker_id_in_transcript] = m.speaker_profile_id
  })
  return out
})

const speakerSelectOptions = computed(() => {
  const opts = [{ value: '', label: '-- Unassigned --' }]
  speakers.value.forEach((s) => {
    opts.push({ value: s.id, label: displayName(s) })
  })
  opts.push({ value: '__new__', label: '+ Create new profile' })
  return opts
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
  apiFetch('/api/admin/transcripts/' + transcriptId.value)
    .then((r) => {
      if (r.status === 401) return Promise.reject(new Error('Unauthorized'))
      return r.ok ? r.json() : Promise.reject(new Error(r.statusText))
    })
    .then((data) => {
      transcript.value = data.transcript
      mappings.value = data.mappings || []
      speakerStats.value = data.speaker_stats || []
      segments.value = data.segments || []
      const groupId = transcript.value?.group_id
      const speakersUrl = groupId
        ? '/api/admin/speakers?group_id=' + encodeURIComponent(groupId)
        : '/api/admin/speakers'
      return Promise.all([
        Promise.resolve(data),
        apiFetch(speakersUrl).then((r) => (r.ok ? r.json() : [])),
        fetch('/api/stat-definitions').then((r) => (r.ok ? r.json() : [])),
      ])
    })
    .then(([data, speakerList, defs]) => {
      statDefinitions.value = Array.isArray(defs) ? defs : []
      speakers.value = speakerList || []
      if (transcript.value.video_path && transcript.value.video_path.trim().startsWith('s3://')) {
        s3UriInput.value = transcript.value.video_path
      }
      tryAutoLoadVideo()
    })
    .catch((e) => {
      if (e.message === 'Unauthorized') {
        clearAuth()
        router.push('/admin?expired=1')
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
    .then((r) => {
      if (r.status === 401) {
        clearAuth()
        router.push('/admin?expired=1')
        return
      }
      return r.ok ? r.json() : r.json().then((j) => Promise.reject(new Error(j.detail || r.statusText)))
    })
    .then((data) => {
      if (!data) return
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
    .then((r) => {
      if (r.status === 401) {
        clearAuth()
        router.push('/admin?expired=1')
        return
      }
      return r.ok ? r.json() : r.json().then((j) => Promise.reject(new Error(j.detail || r.statusText)))
    })
    .then((data) => {
      if (!data) return
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

function onMappingChangeValue(speakerId, val) {
  if (val === '__new__') {
    creatingForSpeakerId.value = speakerId
    showNewSpeaker.value = true
    return
  }
  const profileId = (val && val !== '') ? val : null
  const existing = mappings.value.find((m) => m.speaker_id_in_transcript === speakerId)
  if (existing) {
    existing.speaker_profile_id = profileId
  } else {
    mappings.value.push({ speaker_id_in_transcript: speakerId, speaker_profile_id: profileId })
  }
}

function createAndAssign() {
  const first = newFirstName.value.trim()
  const last = newSurname.value.trim()
  if (!first || !last) return
  const groupId = transcript.value?.group_id
  if (!groupId) {
    saveStatus.value = 'Transcript has no group. Cannot add speaker.'
    return
  }
  apiFetch('/api/admin/speakers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      first_name: first,
      surname: last,
      group_id: groupId,
      slug: newSlug.value.trim() || null,
      short_description: newShortDescription.value.trim() || null,
    }),
  })
    .then((r) => {
      if (r.status === 401) {
        clearAuth()
        router.push('/admin?expired=1')
        return
      }
      return r.ok ? r.json() : Promise.reject(new Error(r.statusText))
    })
    .then((profile) => {
      if (!profile) return
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
    .then((r) => {
      if (r.status === 401) {
        clearAuth()
        router.push('/admin?expired=1')
        return
      }
      return r.ok ? r.json() : Promise.reject(new Error(r.statusText))
    })
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
.mb-3 { margin-bottom: 1rem; }
.mb-4 { margin-bottom: 1.5rem; }
.mt-0 { margin-top: 0; }
.mt-2 { margin-top: 0.5rem; }
.block { display: block; }
.mapping { display: flex; align-items: center; gap: 0.75rem; margin: 0.5rem 0; flex-wrap: wrap; }
.mapping-label { margin: 0; font-weight: normal; min-width: 100px; cursor: pointer; }
.mapping-label:hover { text-decoration: underline; }
.mapping-select { min-width: 200px; }
.transcript { max-height: 360px; overflow-y: auto; border: 1px solid var(--p-surface-300, #d1d5db); border-radius: var(--p-border-radius, 6px); padding: 0.5rem; }
.segment { padding: 0.35rem 0.5rem; margin: 2px 0; border-radius: var(--p-border-radius, 6px); cursor: pointer; }
.segment:hover { background: var(--p-surface-100, #f3f4f6); }
.segment.current { background: var(--p-primary-100, #dbeafe); }
.segment.highlight { background: var(--p-yellow-100, #fef3c7); }
.segment .time { font-size: 0.85em; opacity: 0.85; margin-right: 0.5rem; }
.segment .speaker { font-weight: 600; margin-right: 0.5rem; }
.speaker-stat-card {
  border: 1px solid var(--p-surface-200, #e5e7eb);
  border-radius: 6px;
  padding: 1rem;
  margin-bottom: 1rem;
}
.speaker-stat-id { margin: 0 0 0.5rem 0; font-size: 1rem; }
.speaker-stat-group { margin-top: 0.75rem; }
.speaker-stat-group .group-label { font-weight: 600; font-size: 0.9rem; }
.stat-list { list-style: none; padding: 0; margin: 0.25rem 0 0 0.5rem; }
.stat-line { display: flex; justify-content: space-between; gap: 1rem; padding: 0.2rem 0; font-size: 0.9rem; }
.stat-label { opacity: 0.85; }
.stat-value { font-weight: 500; }
</style>
