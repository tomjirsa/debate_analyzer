import { createRouter, createWebHistory } from 'vue-router'
import { ADMIN_AUTH_KEY } from '../composables/useAdminAuth'
import HomeView from '../views/HomeView.vue'
import GroupDashboardView from '../views/GroupDashboardView.vue'
import SpeakerView from '../views/SpeakerView.vue'
import AdminView from '../views/AdminView.vue'
import AdminGroupsView from '../views/AdminGroupsView.vue'
import AdminTranscriptsView from '../views/AdminTranscriptsView.vue'
import AdminSpeakersView from '../views/AdminSpeakersView.vue'
import AdminAnnotateView from '../views/AdminAnnotateView.vue'

const router = createRouter({
  history: createWebHistory('/'),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/group/:idOrSlug', name: 'group-dashboard', component: GroupDashboardView },
    { path: '/group/:groupId/speakers/:idOrSlug', name: 'group-speaker', component: SpeakerView },
    { path: '/speakers/:idOrSlug', name: 'speaker', component: SpeakerView },
    { path: '/admin', name: 'admin', component: AdminView },
    { path: '/admin/groups', name: 'admin-groups', component: AdminGroupsView },
    { path: '/admin/transcripts', name: 'admin-transcripts', component: AdminTranscriptsView },
    { path: '/admin/speakers', name: 'admin-speakers', component: AdminSpeakersView },
    { path: '/admin/annotate', name: 'admin-annotate', component: AdminAnnotateView },
  ],
})

router.beforeEach((to) => {
  if (to.path.startsWith('/admin') && to.path !== '/admin') {
    try {
      if (!sessionStorage.getItem(ADMIN_AUTH_KEY)) {
        return { path: '/admin' }
      }
    } catch (_) {
      return { path: '/admin' }
    }
  }
})

export default router
