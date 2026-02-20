import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import SpeakerView from '../views/SpeakerView.vue'
import AdminView from '../views/AdminView.vue'
import AdminTranscriptsView from '../views/AdminTranscriptsView.vue'
import AdminSpeakersView from '../views/AdminSpeakersView.vue'
import AdminAnnotateView from '../views/AdminAnnotateView.vue'

const router = createRouter({
  history: createWebHistory('/'),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/speakers/:idOrSlug', name: 'speaker', component: SpeakerView },
    { path: '/admin', name: 'admin', component: AdminView },
    { path: '/admin/transcripts', name: 'admin-transcripts', component: AdminTranscriptsView },
    { path: '/admin/speakers', name: 'admin-speakers', component: AdminSpeakersView },
    { path: '/admin/annotate', name: 'admin-annotate', component: AdminAnnotateView },
  ],
})

export default router
