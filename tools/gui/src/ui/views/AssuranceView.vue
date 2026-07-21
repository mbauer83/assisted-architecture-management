<script setup lang="ts">
import { ref, onMounted } from 'vue'

interface AssuranceStatus {
  configured: boolean
  unlocked: boolean
  status: 'unlocked' | 'locked' | 'not_initialised'
  db_path?: string
  hint?: string | null
}

const status = ref<AssuranceStatus | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    const resp = await fetch('/api/assurance/status')
    if (resp.ok) {
      status.value = await resp.json() as AssuranceStatus
    } else {
      error.value = `Failed to fetch assurance status (${resp.status})`
    }
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="assurance-view">
    <div class="assurance-header">
      <h1 class="assurance-title">
        Assurance
      </h1>
      <p class="assurance-subtitle">
        STPA / CAST / GRC analysis — confidential, traceable, auditable
      </p>
    </div>

    <div
      v-if="loading"
      class="assurance-loading"
    >
      Loading assurance store status…
    </div>

    <div
      v-else-if="error"
      class="assurance-error"
    >
      <p>{{ error }}</p>
    </div>

    <template v-else-if="status">
      <!-- Locked banner -->
      <div
        v-if="status.status !== 'unlocked'"
        class="assurance-banner"
        :class="`assurance-banner--${status.status}`"
      >
        <div class="assurance-banner__icon">
          🔒
        </div>
        <div class="assurance-banner__body">
          <p class="assurance-banner__title">
            {{ status.status === 'not_initialised' ? 'Assurance store not initialised' : 'Assurance store locked' }}
          </p>
          <p class="assurance-banner__hint">
            <template v-if="status.status === 'not_initialised'">
              Run <code>arch-assurance init</code> in your workspace to enable the confidential assurance capability.
            </template>
            <template v-else>
              Run <code>arch-assurance unlock</code> and restart the backend to enable assurance tools.
            </template>
          </p>
        </div>
      </div>

      <!-- Unlocked state -->
      <div
        v-else
        class="assurance-unlocked"
      >
        <div class="assurance-banner assurance-banner--unlocked">
          <div class="assurance-banner__icon">
            🔓
          </div>
          <div class="assurance-banner__body">
            <p class="assurance-banner__title">
              Assurance store unlocked
            </p>
            <p class="assurance-banner__hint">
              Browse and inspect assurance nodes, or use the arch-assurance MCP tools to author analyses.
            </p>
          </div>
        </div>
        <div class="assurance-links">
          <RouterLink
            to="/assurance/stpa"
            class="assurance-link"
          >
            STPA wizard →
          </RouterLink>
          <RouterLink
            to="/assurance/grc"
            class="assurance-link"
          >
            GRC wizard →
          </RouterLink>
          <RouterLink
            to="/assurance/cast"
            class="assurance-link"
          >
            CAST wizard →
          </RouterLink>
          <RouterLink
            to="/assurance/supply-chain"
            class="assurance-link"
          >
            Supply-chain wizard →
          </RouterLink>
          <RouterLink
            to="/assurance/gsn"
            class="assurance-link"
          >
            Assurance-case / GSN wizard →
          </RouterLink>
          <RouterLink
            to="/assurance/browse"
            class="assurance-link"
          >
            Browse assurance nodes →
          </RouterLink>
          <RouterLink
            to="/assurance/graph"
            class="assurance-link"
          >
            Graph explorer →
          </RouterLink>
          <RouterLink
            to="/assurance/diagrams"
            class="assurance-link"
          >
            Derived diagrams →
          </RouterLink>
          <RouterLink
            to="/assurance/baselines"
            class="assurance-link"
          >
            Sealed baselines →
          </RouterLink>
        </div>
      </div>

      <!-- Getting started -->
      <div class="assurance-getting-started">
        <h2>Getting started</h2>
        <ol>
          <li>Run <code>arch-assurance init</code> to create the encrypted assurance store.</li>
          <li>Run <code>arch-assurance unlock</code> and restart <code>arch-backend</code>.</li>
          <li>Use the <strong>stpa-analysis</strong> skill (Phase 2) or the <code>arch-assurance-write</code> MCP tools to begin a STPA analysis.</li>
          <li>Use <code>assurance_guidance</code> (MCP read tool) for per-step method coaching.</li>
        </ol>
        <p class="assurance-note">
          Assurance analyses are stored in an encrypted SQLite database (SQLCipher) separate from the
          architecture git repository. References flow one way: assurance → architecture only.
        </p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.assurance-view { max-width: 800px; margin: 0 auto; padding: 32px 24px; }
.assurance-header { margin-bottom: 24px; }
.assurance-title { font-size: 24px; font-weight: 700; margin: 0 0 6px; }
.assurance-subtitle { color: #64748b; margin: 0; }
.assurance-loading, .assurance-error { color: #64748b; padding: 16px 0; }
.assurance-banner {
  display: flex; align-items: flex-start; gap: 16px;
  padding: 16px 20px; border-radius: 8px; margin-bottom: 24px;
  border: 1px solid #e2e8f0;
}
.assurance-banner--not_initialised { background: #fef3c7; border-color: #fcd34d; }
.assurance-banner--locked { background: #fee2e2; border-color: #fca5a5; }
.assurance-banner--unlocked { background: #dcfce7; border-color: #86efac; }
.assurance-banner__icon { font-size: 24px; flex-shrink: 0; margin-top: 2px; }
.assurance-banner__title { font-weight: 600; margin: 0 0 6px; }
.assurance-banner__hint { margin: 0; font-size: 14px; color: #374151; }
.assurance-banner__hint code { background: rgba(0,0,0,.07); padding: 1px 5px; border-radius: 3px; }
.assurance-links { margin-bottom: 24px; display: flex; gap: 12px; }
.assurance-link { font-weight: 500; color: #2563eb; }
.assurance-getting-started { border-top: 1px solid #e2e8f0; padding-top: 24px; }
.assurance-getting-started h2 { font-size: 16px; font-weight: 600; margin: 0 0 12px; }
.assurance-getting-started ol { padding-left: 20px; line-height: 1.8; }
.assurance-getting-started code { background: #f1f5f9; padding: 1px 5px; border-radius: 3px; font-size: 13px; }
.assurance-note { margin-top: 16px; font-size: 13px; color: #64748b; }
</style>
