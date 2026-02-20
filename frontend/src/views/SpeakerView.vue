<template>
  <div>
    <p><router-link to="/">← Dashboard</router-link></p>
    <div v-if="error" class="err">{{ error }}</div>
    <div v-else-if="profile">
      <h1>{{ displayName }}</h1>
      <p v-if="profile.short_description" class="short-desc">{{ profile.short_description }}</p>
      <p v-if="profile.bio">{{ profile.bio }}</p>
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
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const profile = ref(null)
const stats = ref({ transcript_count: 0, segment_count: 0, total_seconds: 0, word_count: 0 })
const error = ref('')

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
  const s = Number(sec) || 0
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return (h ? h + ' h ' : '') + m + ' min'
}

onMounted(async () => {
  const id = route.params.idOrSlug
  if (!id) {
    error.value = 'No speaker ID.'
    return
  }
  try {
    const r = await fetch('/api/speakers/' + encodeURIComponent(id))
    if (r.status === 404) throw new Error('Speaker not found')
    if (!r.ok) throw new Error(r.statusText)
    const data = await r.json()
    profile.value = data.profile
    stats.value = data.stats
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
.stat {
  background: #f5f5f5;
  padding: 0.75rem;
  border-radius: 6px;
}
.stat .value { font-size: 1.25rem; font-weight: 600; }
.stat .label { font-size: 0.85rem; color: #666; }
</style>
