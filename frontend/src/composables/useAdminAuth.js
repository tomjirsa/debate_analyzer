import { ref } from 'vue'

export const ADMIN_AUTH_KEY = 'debate_analyzer_admin_auth'

function getStoredAuth() {
  try {
    return typeof sessionStorage !== 'undefined' && !!sessionStorage.getItem(ADMIN_AUTH_KEY)
  } catch (_) {
    return false
  }
}

const isLoggedIn = ref(getStoredAuth())

export function useAdminAuth() {
  function setAuth(username, password) {
    try {
      const encoded = btoa(unescape(encodeURIComponent(`${username}:${password}`)))
      sessionStorage.setItem(ADMIN_AUTH_KEY, encoded)
      isLoggedIn.value = true
    } catch (_) {}
  }

  function clearAuth() {
    try {
      sessionStorage.removeItem(ADMIN_AUTH_KEY)
      isLoggedIn.value = false
    } catch (_) {}
  }

  function getAuthHeader() {
    try {
      const raw = sessionStorage.getItem(ADMIN_AUTH_KEY)
      return raw ? `Basic ${raw}` : null
    } catch (_) {
      return null
    }
  }

  function apiFetch(url, options = {}) {
    const headers = { ...(options.headers || {}) }
    const auth = getAuthHeader()
    if (auth) headers['Authorization'] = auth
    return fetch(url, { credentials: 'include', ...options, headers })
  }

  return { setAuth, clearAuth, getAuthHeader, apiFetch, isLoggedIn }
}
