<script setup lang="ts">
import { RouterView } from 'vue-router'
import { inject, provide, ref, onMounted, onUnmounted, computed } from 'vue'
import { Effect } from 'effect'
import { modelServiceKey } from './keys'
import NavBar from './components/NavBar.vue'
import ToastStack from './components/ToastStack.vue'
import SaveChangesDialog from './components/SaveChangesDialog.vue'
import type { SyncStatus } from '../domain'

type SaveMode = 'engagement-save' | 'enterprise-save' | 'enterprise-submit' | 'enterprise-withdraw'

const svc = inject(modelServiceKey)!
const adminMode = ref(false)
const readOnly = ref(false)
const writeBlocked = ref(false)
const syncStatus = ref<SyncStatus | null>(null)
const saveDialogMode = ref<SaveMode | null>(null)

const toasts = ref<Array<{id: number; message: string; type: 'info'|'warn'|'error'}>>([])
let toastCounter = 0

const addToast = (message: string, type: 'info'|'warn'|'error' = 'info', durationMs = 4000) => {
  const id = ++toastCounter
  toasts.value.push({ id, message, type })
  setTimeout(() => { toasts.value = toasts.value.filter(t => t.id !== id) }, durationMs)
}

const anyWriteBlocked = computed(() => readOnly.value || writeBlocked.value)
const engDirty = computed(() => syncStatus.value?.engagement?.has_uncommitted_changes ?? false)
const entStatus = computed(() => syncStatus.value?.enterprise ?? null)

const loadSyncStatus = () => {
  Effect.runPromise(svc.getSyncStatus()).then(s => { syncStatus.value = s }).catch(() => {})
}

let eventSource: EventSource | null = null

onMounted(() => {
  Effect.runPromise(svc.getServerInfo())
    .then((info: any) => { adminMode.value = Boolean(info?.admin_mode); readOnly.value = Boolean(info?.read_only) })
    .catch(() => {})

  loadSyncStatus()

  try {
    eventSource = new EventSource('/api/events')

    eventSource.addEventListener('write_block_changed', (e) => {
      const data = JSON.parse(e.data)
      writeBlocked.value = data.blocked
      addToast(data.blocked ? 'Sync in progress — writes paused' : 'Sync complete — writes resumed', data.blocked ? 'warn' : 'info')
    })
    eventSource.addEventListener('git_sync_started', () => { addToast('Pulling updates…', 'info') })
    eventSource.addEventListener('git_sync_completed', (e) => {
      const data = JSON.parse(e.data)
      addToast(`Pulled ${data.commits_pulled} commit(s)`, 'info')
    })
    eventSource.addEventListener('git_sync_failed', (e) => {
      const data = JSON.parse(e.data)
      addToast(`Sync failed: ${data.error}. Writes resume in ${data.auto_unblock_in_seconds}s`, 'error', 7000)
    })

    const onSyncEvent = (label: string) => () => { addToast(label, 'info'); loadSyncStatus() }
    eventSource.addEventListener('sync_engagement_saved', onSyncEvent('Engagement changes saved'))
    eventSource.addEventListener('sync_enterprise_saved', onSyncEvent('Enterprise changes saved'))
    eventSource.addEventListener('sync_enterprise_submitted', onSyncEvent('Enterprise submission ready'))
    eventSource.addEventListener('sync_enterprise_withdrawn', onSyncEvent('Enterprise submission withdrawn'))
  } catch (err) {
    console.error('Failed to connect to event stream:', err)
  }

  provide('writeBlocked', anyWriteBlocked)
})

onUnmounted(() => { if (eventSource) eventSource.close() })
</script>

<template>
  <NavBar
    :admin-mode="adminMode"
    :read-only="readOnly"
    :eng-dirty="engDirty"
    :ent-status="entStatus"
    @open-save-dialog="saveDialogMode = $event"
  />

  <output v-if="adminMode" class="admin-banner">
    <strong>Admin mode</strong> — writes to both repositories are permitted.
    Use the <strong>Save</strong> and <strong>Submit</strong> controls in the Global nav to commit and submit enterprise changes.
  </output>

  <output v-if="readOnly" class="readonly-banner">
    <strong>Read-only mode</strong> — write operations are disabled.
  </output>

  <main class="main">
    <RouterView />
  </main>

  <ToastStack :toasts="toasts" />

  <SaveChangesDialog
    v-if="saveDialogMode"
    :mode="saveDialogMode"
    :sync-status="syncStatus"
    @close="saveDialogMode = null"
    @done="(msg) => { addToast(msg); loadSyncStatus() }"
  />
</template>

<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, -apple-system, sans-serif; font-size: 14px; line-height: 1.5; color: #1a1a1a; background: #f5f5f5; }
a { color: #2563eb; text-decoration: none; }
a:hover { text-decoration: underline; }
pre, code { font-family: 'Cascadia Code', 'Fira Code', monospace; font-size: 13px; }
</style>

<style scoped>
.admin-banner { background: #7c2d12; color: #fed7aa; padding: 7px 24px; font-size: 13px; line-height: 1.5; border-bottom: 2px solid #ea580c; }
.admin-banner strong { color: #fb923c; font-weight: 700; }
.readonly-banner { background: #1e3a5f; color: #bfdbfe; padding: 7px 24px; font-size: 13px; line-height: 1.5; border-bottom: 2px solid #3b82f6; }
.readonly-banner strong { color: #93c5fd; font-weight: 700; }
.main { max-width: 1200px; margin: 0 auto; padding: 24px; }
</style>
