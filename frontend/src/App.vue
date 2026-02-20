<template>
  <div>
    <header class="site-header">
      <router-link to="/" class="site-title">Debate Analyzer</router-link>
      <nav class="site-nav">
        <router-link to="/">Speakers</router-link>
        <router-link to="/admin">Admin</router-link>
      </nav>
    </header>
    <main class="site-main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
</script>

<style scoped>
.site-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.75rem;
  padding: 0.75rem 0;
  margin-bottom: 1rem;
  border-bottom: 1px solid #eee;
}
.site-title {
  font-weight: 600;
  color: inherit;
  text-decoration: none;
}
.site-title:hover {
  text-decoration: underline;
}
.site-nav {
  display: flex;
  gap: 1rem;
}
.site-nav a {
  color: #0d6efd;
  text-decoration: none;
}
.site-nav a:hover {
  text-decoration: underline;
}
.site-main {
  /* main content uses existing max-width from body / global */
}
</style>
