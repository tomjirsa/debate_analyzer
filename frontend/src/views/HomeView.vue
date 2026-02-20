<template>
  <div>
    <h1>Dashboard</h1>
    <p>Main statistics and speakers in the debate database.</p>
    <ul v-if="speakers.length" id="speakers">
      <li v-for="s in speakers" :key="s.id">
        <router-link :to="'/speakers/' + encodeURIComponent(s.slug || s.id)">
          {{ displayName(s) }}
        </router-link>
      </li>
    </ul>
    <p v-else-if="!loading && !error" class="empty">No speakers yet. Register transcripts and assign speakers in the admin.</p>
    <p v-if="error" id="loadErr" class="err">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const speakers = ref([])
const loading = ref(true)
const error = ref('')

function displayName(s) {
  if (s.first_name && s.surname) return `${s.first_name} ${s.surname}`
  return s.display_name || s.id
}

onMounted(async () => {
  try {
    const r = await fetch('/api/speakers')
    if (!r.ok) throw new Error(r.statusText)
    speakers.value = await r.json()
  } catch (e) {
    error.value = 'Failed to load speakers: ' + e.message
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.empty { color: #666; }
</style>
