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
        <div v-else class="group-grid">
          <router-link
            v-for="g in groups"
            :key="g.id"
            :to="'/group/' + encodeURIComponent(g.slug || g.id)"
            class="group-card-link"
          >
            <DashboardCard>
              <template #title>{{ g.name }}</template>
              <template #content>
                <p v-if="g.description" class="group-desc">{{ g.description }}</p>
              </template>
            </DashboardCard>
          </router-link>
        </div>
      </template>
    </Card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import Card from 'primevue/card'
import Message from 'primevue/message'
import ProgressSpinner from 'primevue/progressspinner'
import DashboardCard from '../components/DashboardCard.vue'

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
.group-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 1rem;
}

.group-card-link {
  text-decoration: none;
  display: block;
}

.group-card-link:hover .dashboard-widget {
  border-color: var(--p-primary-300, #a5b4fc);
}

.group-desc {
  margin: 0;
  font-size: 0.9rem;
  color: var(--p-text-muted-color, #6b7280);
}
</style>
