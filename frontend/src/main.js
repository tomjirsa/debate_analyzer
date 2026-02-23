import { createApp } from 'vue'
import PrimeVue from 'primevue/config'
import ConfirmationService from 'primevue/confirmationservice'
import App from './App.vue'
import router from './router'
import { AnalyticsPreset } from './theme/analytics-preset'
import 'primeicons/primeicons.css'
import './assets/main.css'

// Apply saved theme before mount so first paint uses correct scheme
const savedTheme = localStorage.getItem('debate-analyzer-theme')
if (savedTheme === 'dark') {
  document.documentElement.classList.add('app-dark')
} else {
  document.documentElement.classList.remove('app-dark')
}

const app = createApp(App)
app.use(PrimeVue, {
  theme: {
    preset: AnalyticsPreset,
    options: {
      darkModeSelector: '.app-dark',
    },
  },
  ripple: true,
})
app.use(ConfirmationService)
app.use(router)
app.mount('#app')
