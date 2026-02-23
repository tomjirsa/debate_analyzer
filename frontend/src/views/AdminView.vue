<template>
  <div>
    <p class="mb-3">
      <router-link to="/">← Dashboard</router-link>
    </p>

    <Card>
      <template #title>Admin</template>
      <template #content>
        <div v-if="showLogin" class="login-box">
          <h3 class="mt-0">Admin login</h3>
          <Message v-if="sessionExpired" severity="warn" class="mb-2">Session expired. Please log in again.</Message>
          <p>Enter the admin username and password configured on the server.</p>
          <div class="flex flex-column gap-2">
            <label for="loginUser">Username</label>
            <InputText
              id="loginUser"
              v-model="loginUser"
              type="text"
              placeholder="username"
              autocomplete="username"
              class="w-full max-w-20rem"
            />
            <label for="loginPass">Password</label>
            <Password
              id="loginPass"
              v-model="loginPass"
              placeholder="password"
              :feedback="false"
              toggle-mask
              class="w-full max-w-20rem"
              input-class="w-full"
            />
            <Button label="Log in" @click="doLogin" />
            <Message v-if="loginErr" severity="error">{{ loginErr }}</Message>
          </div>
        </div>

        <template v-else>
          <Panel header="Admin" class="dashboard-panel">
            <ul class="dashboard-links">
              <li>
                <router-link to="/admin/transcripts">Transcript Registration Management</router-link>
                — Register, update, or delete transcripts.
              </li>
              <li>
                <router-link to="/admin/speakers">Manage speakers</router-link>
                — Add, edit, or delete speaker profiles.
              </li>
            </ul>
          </Panel>
        </template>
      </template>
    </Card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import Button from 'primevue/button'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Panel from 'primevue/panel'
import Password from 'primevue/password'
import { useAdminAuth } from '../composables/useAdminAuth'

const route = useRoute()
const { setAuth, clearAuth, apiFetch, isLoggedIn } = useAdminAuth()

const showLogin = computed(() => !isLoggedIn.value)
const sessionExpired = computed(() => route.query.expired === '1')
const loginUser = ref('')
const loginPass = ref('')
const loginErr = ref('')

function doLogin() {
  loginErr.value = ''
  const user = loginUser.value.trim()
  const pass = loginPass.value
  if (!user || !pass) {
    loginErr.value = 'Enter username and password.'
    return
  }
  setAuth(user, pass)
  apiFetch('/api/admin/transcripts')
    .then((r) => {
      if (r.status === 401) {
        clearAuth()
        loginErr.value = 'Invalid username or password.'
        return
      }
      if (!r.ok) throw new Error(r.statusText)
      return r.json()
    })
    .then(() => {})
    .catch((e) => { loginErr.value = e.message })
}

function loadTranscripts() {
  apiFetch('/api/admin/transcripts')
    .then((r) => {
      if (r.status === 401) clearAuth()
    })
    .catch(() => {})
}

onMounted(loadTranscripts)
</script>

<style scoped>
.mb-3 { margin-bottom: 1rem; }
.mt-0 { margin-top: 0; }
.login-box { max-width: 320px; }
.mb-2 { margin-bottom: 0.5rem; }
.dashboard-links { list-style: none; padding: 0; margin: 0; }
.dashboard-links li { margin: 0.75rem 0; }
.dashboard-links a { text-decoration: none; }
.dashboard-links a:hover { text-decoration: underline; }
</style>
