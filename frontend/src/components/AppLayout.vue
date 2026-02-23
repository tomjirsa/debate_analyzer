<template>
  <div class="app-layout">
    <aside class="app-sidebar">
      <div class="sidebar-brand">
        <router-link to="/" class="sidebar-title">Debate Analyzer</router-link>
      </div>
      <nav class="sidebar-nav">
        <router-link to="/" class="sidebar-item" active-class="sidebar-item-active">
          <i class="pi pi-home"></i>
          <span class="sidebar-item-label">Dashboard</span>
        </router-link>
        <div class="sidebar-group">
          <span class="sidebar-group-label">Admin</span>
          <template v-if="isLoggedIn">
            <router-link to="/admin" class="sidebar-item" active-class="sidebar-item-active">Admin</router-link>
            <router-link to="/admin/transcripts" class="sidebar-item" active-class="sidebar-item-active">Transcripts</router-link>
            <router-link to="/admin/speakers" class="sidebar-item" active-class="sidebar-item-active">Speakers</router-link>
          </template>
          <router-link v-else to="/admin" class="sidebar-item" active-class="sidebar-item-active">Admin login</router-link>
        </div>
      </nav>
    </aside>
    <div class="app-main-wrap">
      <header class="app-topbar">
        <router-link to="/" class="topbar-title">Debate Analyzer</router-link>
        <button
          type="button"
          class="theme-toggle"
          :aria-label="isDark ? 'Switch to light theme' : 'Switch to dark theme'"
          @click="toggleTheme"
        >
          <i :class="isDark ? 'pi pi-sun' : 'pi pi-moon'"></i>
        </button>
      </header>
      <main class="app-main">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAdminAuth } from '../composables/useAdminAuth'

const { isLoggedIn } = useAdminAuth()
const THEME_KEY = 'debate-analyzer-theme'
const isDark = ref(false)

function toggleTheme() {
  isDark.value = !isDark.value
  document.documentElement.classList.toggle('app-dark', isDark.value)
  localStorage.setItem(THEME_KEY, isDark.value ? 'dark' : 'light')
}

onMounted(() => {
  isDark.value = localStorage.getItem(THEME_KEY) === 'dark'
})
</script>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
}

.app-sidebar {
  width: 220px;
  flex-shrink: 0;
  background: var(--p-surface-100, #f3f4f6);
  border-right: 1px solid var(--p-surface-200, #e5e7eb);
  display: flex;
  flex-direction: column;
}

.sidebar-brand {
  padding: 1rem;
  border-bottom: 1px solid var(--p-surface-200, #e5e7eb);
}

.sidebar-title {
  font-weight: 600;
  font-size: 1.05rem;
  text-decoration: none;
  color: var(--p-text-color, inherit);
}

.sidebar-title:hover {
  color: var(--p-primary-color, #2563eb);
}

.sidebar-nav {
  padding: 0.75rem 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sidebar-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 1rem;
  text-decoration: none;
  color: var(--p-text-color, inherit);
  font-size: 0.9rem;
}

.sidebar-item:hover {
  background: var(--p-surface-200, #e5e7eb);
  color: var(--p-primary-color, #2563eb);
}

.sidebar-item-active {
  background: var(--p-highlight-background, #eff6ff);
  color: var(--p-primary-color, #2563eb);
  font-weight: 500;
}

.sidebar-item .pi {
  font-size: 1.1rem;
  flex-shrink: 0;
}

.sidebar-item-label {
  flex: 1;
}

.sidebar-group {
  margin-top: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--p-surface-200, #e5e7eb);
}

.sidebar-group-label {
  display: block;
  padding: 0.25rem 1rem;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--p-text-muted-color, #6b7280);
}

.app-main-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.app-topbar {
  flex-shrink: 0;
  height: 48px;
  padding: 0 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  background: var(--p-surface-0, #fff);
  border-bottom: 1px solid var(--p-surface-200, #e5e7eb);
}

.theme-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.25rem;
  height: 2.25rem;
  padding: 0;
  border: none;
  border-radius: var(--p-border-radius, 6px);
  background: transparent;
  color: var(--p-text-color, inherit);
  cursor: pointer;
}

.theme-toggle:hover {
  background: var(--p-surface-200, #e5e7eb);
  color: var(--p-primary-color, #2563eb);
}

.theme-toggle .pi {
  font-size: 1.2rem;
}

.topbar-title {
  font-weight: 600;
  font-size: 1rem;
  text-decoration: none;
  color: var(--p-text-color, inherit);
}

.topbar-title:hover {
  color: var(--p-primary-color, #2563eb);
}

.app-main {
  flex: 1;
  padding: 1.25rem;
  overflow: auto;
}
</style>
