<template>
  <div>
    <Card>
      <template #title>Dashboard</template>
      <template #subtitle>Main statistics and speakers in the debate database.</template>
      <template #content>
        <ProgressSpinner v-if="loading" aria-label="Loading speakers" />
        <Message v-else-if="error" id="loadErr" severity="error">{{ error }}</Message>
        <Message v-else-if="!speakers.length" severity="info">
          No speakers yet. Register transcripts and assign speakers in the admin.
        </Message>
        <ul v-else id="speakers" class="speaker-list">
          <li v-for="s in speakers" :key="s.id">
            <router-link :to="'/speakers/' + encodeURIComponent(s.slug || s.id)">
              {{ displayName(s) }}
            </router-link>
          </li>
        </ul>
      </template>
    </Card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import Card from 'primevue/card'
import Message from 'primevue/message'
import ProgressSpinner from 'primevue/progressspinner'

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
.speaker-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.speaker-list li {
  margin: 0.5rem 0;
}
.speaker-list a {
  text-decoration: none;
}
.speaker-list a:hover {
  text-decoration: underline;
}
</style>
