<template>
  <div>
    <h1>Admin</h1>
    <p>
      <router-link to="/">← Public speakers</router-link>
    </p>

    <div v-if="showLogin" class="login-box">
      <h2>Admin login</h2>
      <p>Enter the admin username and password configured on the server.</p>
      <label for="loginUser">Username</label>
      <input id="loginUser" v-model="loginUser" type="text" placeholder="username" autocomplete="username">
      <label for="loginPass">Password</label>
      <input id="loginPass" v-model="loginPass" type="password" placeholder="password" autocomplete="current-password">
      <br>
      <button type="button" @click="doLogin">Log in</button>
      <p class="err">{{ loginErr }}</p>
    </div>

    <template v-else>
      <section class="dashboard-links">
        <h2>Admin</h2>
        <ul>
          <li><router-link to="/admin/transcripts">Transcript Registration Management</router-link> — Register, update, or delete transcripts.</li>
          <li><router-link to="/admin/speakers">Manage speakers</router-link> — Add, edit, or delete speaker profiles.</li>
        </ul>
      </section>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAdminAuth } from '../composables/useAdminAuth'

const { setAuth, clearAuth, apiFetch } = useAdminAuth()

const showLogin = ref(false)
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
    .then(() => {
      showLogin.value = false
    })
    .catch((e) => { loginErr.value = e.message })
}

function loadTranscripts() {
  apiFetch('/api/admin/transcripts')
    .then((r) => {
      if (r.status === 401) {
        clearAuth()
        showLogin.value = true
        return
      }
      if (r.ok) showLogin.value = false
    })
    .catch(() => {})
}

onMounted(loadTranscripts)
</script>

<style scoped>
.login-box {
  background: #f0f8ff;
  padding: 1rem;
  border-radius: 6px;
  margin-bottom: 1.5rem;
  max-width: 320px;
}
.login-box input { width: 100%; }
.dashboard-links ul { list-style: none; padding: 0; }
.dashboard-links li { margin: 0.75rem 0; }
</style>
