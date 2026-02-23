<template>
  <div>
    <Card>
      <template #title>Dashboard</template>
      <template #subtitle>Choose a group to view its speakers and statistics.</template>
      <template #content>
        <ProgressSpinner v-if="loading" aria-label="Loading groups" />
        <Message v-else-if="error" id="loadErr" severity="error">{{ error }}</Message>
        <Message v-else-if="!groups.length" severity="info">
          No groups yet. Create a group in the admin, then add transcripts and speakers.
        </Message>
        <ul v-else id="groups" class="group-list">
          <li v-for="g in groups" :key="g.id">
            <router-link :to="'/group/' + encodeURIComponent(g.slug || g.id)">
              {{ g.name }}
            </router-link>
            <span v-if="g.description" class="group-desc">{{ g.description }}</span>
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

const groups = ref([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const r = await fetch('/api/groups')
    if (!r.ok) throw new Error(r.statusText)
    groups.value = await r.json()
  } catch (e) {
    error.value = 'Failed to load groups: ' + e.message
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.group-list { list-style: none; padding: 0; margin: 0; }
.group-list li { margin: 0.75rem 0; display: flex; flex-direction: column; gap: 0.25rem; }
.group-list a { text-decoration: none; font-weight: 500; }
.group-list a:hover { text-decoration: underline; }
.group-desc { font-size: 0.9rem; color: var(--p-text-muted-color, #6b7280); }
</style>
