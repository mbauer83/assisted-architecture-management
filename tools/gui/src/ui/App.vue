<script setup lang="ts">
import { RouterLink, RouterView, useRouter } from 'vue-router'
import { inject, ref, onMounted } from 'vue'
import { Effect } from 'effect'
import { modelServiceKey } from './keys'

const svc = inject(modelServiceKey)!
const router = useRouter()
const adminMode = ref(false)

onMounted(() => {
  Effect.runPromise(svc.getServerInfo())
    .then((info: any) => { adminMode.value = Boolean(info?.admin_mode) })
    .catch(() => {})
})

const searchQuery = ref('')
const submitSearch = () => {
  const q = searchQuery.value.trim()
  if (!q) return
  router.push({ path: '/search', query: { q } })
  searchQuery.value = ''
}
</script>

<template>
  <header class="nav">
    <RouterLink class="nav__brand" to="/">Architecture Repository</RouterLink>

    <div class="nav__sections">
      <!-- Engagement section -->
      <div class="nav__section">
        <span class="nav__section-label">Engagement</span>
        <nav class="nav__links">
          <RouterLink to="/entities">Browse</RouterLink>
          <RouterLink to="/diagrams">Diagrams</RouterLink>
          <RouterLink to="/promote" class="nav__promote">↑ Promote</RouterLink>
        </nav>
      </div>

      <div class="nav__divider" aria-hidden="true"></div>

      <!-- Global (enterprise) section -->
      <div class="nav__section">
        <span class="nav__section-label nav__section-label--global">Global</span>
        <nav class="nav__links">
          <RouterLink to="/global/entities">Browse</RouterLink>
          <RouterLink to="/global/diagrams">Diagrams</RouterLink>
        </nav>
      </div>
    </div>

    <!-- Persistent search bar -->
    <form class="nav__search" @submit.prevent="submitSearch">
      <input
        v-model="searchQuery"
        class="nav__search-input"
        type="search"
        placeholder="Search…"
        aria-label="Search"
      />
    </form>
  </header>

  <!-- Admin mode banner — visible in all views when --admin-mode is active -->
  <div v-if="adminMode" class="admin-banner" role="status">
    <strong>Admin mode</strong> — writes to both repositories are permitted.
    Remember to <code>git commit</code> in the enterprise repository before
    ending this session or restarting in normal mode.
  </div>

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
  gap: 20px;
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
  flex-shrink: 0;
}
.nav__brand:hover { text-decoration: none; color: #93c5fd; }

.nav__sections {
  display: flex;
  align-items: center;
  gap: 0;
  flex: 1;
}

.nav__section {
  display: flex;
  align-items: center;
  gap: 8px;
}

.nav__section-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .07em;
  color: #64748b;
  white-space: nowrap;
  padding: 0 4px;
}

.nav__section-label--global {
  color: #f59e0b;
}

.nav__divider {
  width: 1px;
  height: 20px;
  background: #334155;
  margin: 0 12px;
}

.nav__links {
  display: flex;
  gap: 4px;
}

.nav__links a {
  color: #94a3b8;
  font-size: 13px;
  padding: 4px 8px;
  border-radius: 4px;
}
.nav__links a.router-link-active {
  color: #f8fafc;
  font-weight: 500;
  background: rgba(255,255,255,.08);
}
.nav__links a:hover { color: #e2e8f0; text-decoration: none; background: rgba(255,255,255,.06); }
.nav__promote { color: #fbbf24 !important; }
.nav__promote:hover { color: #f59e0b !important; }

.nav__search { margin-left: auto; display: flex; align-items: center; flex-shrink: 0; }
.nav__search-input {
  width: 180px;
  padding: 5px 10px;
  border-radius: 5px;
  border: 1px solid #334155;
  background: #0f172a;
  color: #f1f5f9;
  font-size: 13px;
  outline: none;
  transition: width .15s, border-color .15s;
}
.nav__search-input::placeholder { color: #64748b; }
.nav__search-input:focus {
  width: 240px;
  border-color: #475569;
  background: #1e293b;
}
.nav__search-input::-webkit-search-cancel-button { display: none; }

.admin-banner {
  background: #7c2d12;
  color: #fed7aa;
  padding: 7px 24px;
  font-size: 13px;
  line-height: 1.5;
  border-bottom: 2px solid #ea580c;
}
.admin-banner strong { color: #fb923c; font-weight: 700; }
.admin-banner code {
  background: rgba(0,0,0,.25);
  border-radius: 3px;
  padding: 1px 5px;
  font-family: monospace;
  font-size: 12px;
  color: #fed7aa;
}

.main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}
</style>
