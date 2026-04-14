<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <header class="nav">
    <RouterLink class="nav__brand" to="/">Architecture Repository</RouterLink>
    <nav class="nav__links">
      <RouterLink to="/">Home</RouterLink>
      <RouterLink to="/entities">Browse</RouterLink>
      <RouterLink to="/search">Search</RouterLink>
    </nav>
  </header>
  <main class="main">
    <RouterView />
  </main>
</template>

<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: system-ui, -apple-system, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  color: #1a1a1a;
  background: #f5f5f5;
}

a { color: #2563eb; text-decoration: none; }
a:hover { text-decoration: underline; }

pre, code {
  font-family: 'Cascadia Code', 'Fira Code', monospace;
  font-size: 13px;
}
</style>

<style scoped>
.nav {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 0 24px;
  height: 48px;
  background: #1e293b;
  color: #f8fafc;
  position: sticky;
  top: 0;
  z-index: 10;
}

.nav__brand {
  font-weight: 600;
  font-size: 15px;
  color: #f8fafc;
  white-space: nowrap;
}
.nav__brand:hover { text-decoration: none; color: #93c5fd; }

.nav__links {
  display: flex;
  gap: 16px;
}
.nav__links a { color: #94a3b8; font-size: 13px; }
.nav__links a.router-link-active { color: #f8fafc; font-weight: 500; }
.nav__links a:hover { color: #e2e8f0; text-decoration: none; }

.main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}
</style>
