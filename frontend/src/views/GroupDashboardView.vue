<template>
  <div>
    <Breadcrumb :model="breadcrumbItems" class="mb-3">
      <template #item="{ item }">
        <router-link v-if="item.to" :to="item.to" class="p-menuitem-link">{{ item.label }}</router-link>
        <span v-else>{{ item.label }}</span>
      </template>
    </Breadcrumb>
    <Card>
      <template #title>{{ group ? group.name : 'Dashboard' }}</template>
      <template #subtitle>{{ group ? (group.description || 'Speakers in this group.') : '' }}</template>
      <template #content>
        <ProgressSpinner v-if="loading" aria-label="Loading" />
        <Message v-else-if="error" id="loadErr" severity="error">{{ error }}</Message>
        <Message v-else-if="group && !speakers.length" severity="info">
          No speakers in this group yet. Add transcripts and assign speakers in the admin.
        </Message>
        <ul v-else-if="group" id="speakers" class="speaker-list">
          <li v-for="s in speakers" :key="s.id">
            <router-link :to="speakerLink(s)">
              {{ displayName(s) }}
            </router-link>
          </li>
        </ul>
      </template>
    </Card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import Card from 'primevue/card'
import Message from 'primevue/message'
import ProgressSpinner from 'primevue/progressspinner'
import Breadcrumb from 'primevue/breadcrumb'

const route = useRoute()
const groupIdOrSlug = computed(() => route.params.idOrSlug)

const group = ref(null)
const speakers = ref([])
const loading = ref(true)
const error = ref('')

const breadcrumbItems = computed(() => {
  const items = [{ label: 'Dashboard', to: '/' }]
  if (group.value) {
    items.push({ label: group.value.name })
  }
  return items
})

function displayName(s) {
  if (s.first_name && s.surname) return `${s.first_name} ${s.surname}`
  return s.display_name || s.id
}

function speakerLink(s) {
  const g = groupIdOrSlug.value
  const id = (s.slug || s.id)
  return `/group/${encodeURIComponent(g)}/speakers/${encodeURIComponent(id)}`
}

async function load() {
  if (!groupIdOrSlug.value) return
  loading.value = true
  error.value = ''
  try {
    const gr = await fetch('/api/groups/' + encodeURIComponent(groupIdOrSlug.value))
    if (!gr.ok) throw new Error(gr.status === 404 ? 'Group not found' : gr.statusText)
    group.value = await gr.json()
    const sr = await fetch('/api/groups/' + encodeURIComponent(groupIdOrSlug.value) + '/speakers')
    if (!sr.ok) throw new Error(sr.statusText)
    speakers.value = await sr.json()
  } catch (e) {
    error.value = e.message
    group.value = null
    speakers.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(groupIdOrSlug, load)
</script>

<style scoped>
.speaker-list { list-style: none; padding: 0; margin: 0; }
.speaker-list li { margin: 0.5rem 0; }
.speaker-list a { text-decoration: none; }
.speaker-list a:hover { text-decoration: underline; }
.mb-3 { margin-bottom: 1rem; }
</style>
