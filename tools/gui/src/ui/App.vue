<script setup lang="ts">
import { RouterView } from 'vue-router'
import { inject, provide, ref, onMounted, onUnmounted, computed } from 'vue'
import { Effect } from 'effect'
import { modelServiceKey, toastKey } from './keys'
import NavBar from './components/NavBar.vue'
import ToastStack from './components/ToastStack.vue'
import SaveChangesDialog from './components/SaveChangesDialog.vue'
import type { SyncStatus } from '../domain'
import { isRecord, readErrorMessage } from './lib/errors'

type SaveMode = 'engagement-save' | 'enterprise-save' | 'enterprise-submit' | 'enterprise-withdraw'

const svc = inject(modelServiceKey)!
const adminMode = ref(false)
const readOnly = ref(false)
const writeBlocked = ref(false)
const syncStatus = ref<SyncStatus | null>(null)
const saveDialogMode = ref<SaveMode | null>(null)
let syncStatusRequestInFlight = false
let queuedSyncStatusRefresh = false
let syncStatusDebounceTimer: ReturnType<typeof setTimeout> | null = null
let syncLeaderLeaseTimer: ReturnType<typeof setInterval> | null = null
let syncLeaderPollTimer: ReturnType<typeof setInterval> | null = null
const syncLeaderTabId = `tab-${Date.now()}-${Math.random().toString(36).slice(2)}`
const SYNC_STATUS_CACHE_KEY = 'arch.gui.sync-status.cache.v1'
const SYNC_STATUS_LEASE_KEY = 'arch.gui.sync-status.lease.v1'
const SYNC_STATUS_LEASE_MS = 90_000
const SYNC_STATUS_LEASE_RENEW_MS = 30_000
const SYNC_STATUS_RECONCILE_MS = 120_000

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
provide('writeBlocked', anyWriteBlocked)
provide(toastKey, addToast)

type SyncStatusCacheEnvelope = { updatedAt: number; status: SyncStatus }
type SyncStatusLease = { tabId: string; expiresAt: number }

const readSyncStatusCache = (): SyncStatusCacheEnvelope | null => {
  try {
    const raw = window.localStorage.getItem(SYNC_STATUS_CACHE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<SyncStatusCacheEnvelope>
    if (!parsed || typeof parsed.updatedAt !== 'number' || typeof parsed.status !== 'object') return null
    return { updatedAt: parsed.updatedAt, status: parsed.status }
  } catch {
    return null
  }
}

const publishSyncStatusCache = (status: SyncStatus) => {
  try {
    const envelope: SyncStatusCacheEnvelope = { updatedAt: Date.now(), status }
    window.localStorage.setItem(SYNC_STATUS_CACHE_KEY, JSON.stringify(envelope))
  } catch {
    // Ignore localStorage quota/privacy failures; the local tab still updates.
  }
}

const readSyncLease = (): SyncStatusLease | null => {
  try {
    const raw = window.localStorage.getItem(SYNC_STATUS_LEASE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<SyncStatusLease>
    if (!parsed || typeof parsed.tabId !== 'string' || typeof parsed.expiresAt !== 'number') return null
    return { tabId: parsed.tabId, expiresAt: parsed.expiresAt }
  } catch {
    return null
  }
}

const stopSyncLeaderPoll = () => {
  if (syncLeaderPollTimer !== null) {
    clearInterval(syncLeaderPollTimer)
    syncLeaderPollTimer = null
  }
}

const startSyncLeaderPoll = () => {
  if (syncLeaderPollTimer !== null) return
  syncLeaderPollTimer = setInterval(() => { loadSyncStatus() }, SYNC_STATUS_RECONCILE_MS)
}

const updateSyncLeaderRole = (isLeader: boolean) => {
  if (isLeader) startSyncLeaderPoll()
  else stopSyncLeaderPoll()
}

const tryAcquireSyncLease = (): void => {
  const now = Date.now()
  const current = readSyncLease()
  if (current && current.tabId !== syncLeaderTabId && current.expiresAt > now) {
    updateSyncLeaderRole(false)
    return
  }
  try {
    const nextLease: SyncStatusLease = {
      tabId: syncLeaderTabId,
      expiresAt: now + SYNC_STATUS_LEASE_MS,
    }
    window.localStorage.setItem(SYNC_STATUS_LEASE_KEY, JSON.stringify(nextLease))
    const confirmed = readSyncLease()
    updateSyncLeaderRole(confirmed?.tabId === syncLeaderTabId)
  } catch {
    updateSyncLeaderRole(true)
  }
}

const loadSyncStatus = () => {
  if (syncStatusRequestInFlight) {
    queuedSyncStatusRefresh = true
    return
  }
  syncStatusRequestInFlight = true
  void Effect.runPromise(svc.getSyncStatus())
    .then((status) => {
      syncStatus.value = status
      publishSyncStatusCache(status)
    })
    .catch((error: unknown) => {
      addToast(`Failed to load sync status: ${readErrorMessage(error)}`, 'error')
    })
    .finally(() => {
      syncStatusRequestInFlight = false
      if (queuedSyncStatusRefresh) {
        queuedSyncStatusRefresh = false
        loadSyncStatus()
      }
    })
}

const scheduleSyncStatusRefresh = (delayMs = 150) => {
  if (syncStatusDebounceTimer !== null) {
    clearTimeout(syncStatusDebounceTimer)
  }
  syncStatusDebounceTimer = setTimeout(() => {
    syncStatusDebounceTimer = null
    loadSyncStatus()
  }, delayMs)
}

const onStorageChanged = (event: StorageEvent) => {
  if (event.key === SYNC_STATUS_CACHE_KEY && event.newValue) {
    const cached = readSyncStatusCache()
    if (cached) syncStatus.value = cached.status
  }
  if (event.key === SYNC_STATUS_LEASE_KEY) {
    const lease = readSyncLease()
    updateSyncLeaderRole(lease?.tabId === syncLeaderTabId)
  }
}

type WriteBlockChangedEvent = { blocked: boolean }
type SyncPullCompletedEvent = { commits_pulled: number }
type SyncPullFailedEvent = { error: string; auto_unblock_in_seconds: number }

const parseEventData = <T extends Record<string, unknown>>(
  raw: string,
  guard: (value: Record<string, unknown>) => value is T,
): T | null => {
  try {
    const parsed = JSON.parse(raw) as unknown
    if (isRecord(parsed) && guard(parsed)) {
      return parsed
    }
  } catch {
    return null
  }
  return null
}

const isWriteBlockChangedEvent = (value: Record<string, unknown>): value is WriteBlockChangedEvent =>
  typeof value.blocked === 'boolean'

const isSyncPullCompletedEvent = (value: Record<string, unknown>): value is SyncPullCompletedEvent =>
  typeof value.commits_pulled === 'number'

const isSyncPullFailedEvent = (value: Record<string, unknown>): value is SyncPullFailedEvent =>
  typeof value.error === 'string' && typeof value.auto_unblock_in_seconds === 'number'

let eventSource: EventSource | null = null

onMounted(() => {
  void Effect.runPromise(svc.getServerInfo())
    .then((info) => {
      adminMode.value = info.admin_mode
      readOnly.value = info.read_only
    })
    .catch((error: unknown) => {
      addToast(`Failed to load server info: ${readErrorMessage(error)}`, 'error')
    })

  const cachedSyncStatus = readSyncStatusCache()
  if (cachedSyncStatus) syncStatus.value = cachedSyncStatus.status
  loadSyncStatus()
  tryAcquireSyncLease()
  syncLeaderLeaseTimer = setInterval(() => { tryAcquireSyncLease() }, SYNC_STATUS_LEASE_RENEW_MS)
  window.addEventListener('storage', onStorageChanged)

  try {
    eventSource = new EventSource('/api/events')

    eventSource.addEventListener('write_block_changed', (e: MessageEvent<string>) => {
      const data = parseEventData(e.data, isWriteBlockChangedEvent)
      if (!data) {
        addToast('Received malformed write-block event', 'error')
        return
      }
      writeBlocked.value = data.blocked
      addToast(
        data.blocked ? 'Sync in progress — writes paused' : 'Sync complete — writes resumed',
        data.blocked ? 'warn' : 'info',
      )
    })
    eventSource.addEventListener('sync_pull_started', () => { addToast('Pulling updates…', 'info') })
    eventSource.addEventListener('sync_pull_completed', (e: MessageEvent<string>) => {
      const data = parseEventData(e.data, isSyncPullCompletedEvent)
      if (!data) {
        addToast('Received malformed sync-complete event', 'error')
        return
      }
      addToast(`Pulled ${data.commits_pulled} commit(s)`, 'info')
      scheduleSyncStatusRefresh()
    })
    eventSource.addEventListener('sync_pull_failed', (e: MessageEvent<string>) => {
      const data = parseEventData(e.data, isSyncPullFailedEvent)
      if (!data) {
        addToast('Received malformed sync-failure event', 'error')
        return
      }
      addToast(`Sync failed: ${data.error}. Writes resume in ${data.auto_unblock_in_seconds}s`, 'error', 7000)
    })

    const onSyncEvent = (label: string) => () => { addToast(label, 'info'); scheduleSyncStatusRefresh() }
    eventSource.addEventListener('sync_engagement_saved', onSyncEvent('Engagement changes saved'))
    eventSource.addEventListener('sync_enterprise_saved', onSyncEvent('Enterprise changes saved'))
    eventSource.addEventListener('sync_enterprise_submitted', onSyncEvent('Enterprise submission ready'))
    eventSource.addEventListener('sync_enterprise_withdrawn', onSyncEvent('Enterprise submission withdrawn'))
    eventSource.addEventListener('sync_status_changed', () => { scheduleSyncStatusRefresh() })
    eventSource.addEventListener('sync_repository_updated', () => { scheduleSyncStatusRefresh() })
    eventSource.addEventListener('artifact_write_completed', () => { scheduleSyncStatusRefresh() })
  } catch (err) {
    console.error('Failed to connect to event stream:', err)
  }
})

onUnmounted(() => {
  if (eventSource) {
    eventSource.close()
  }
  if (syncStatusDebounceTimer !== null) {
    clearTimeout(syncStatusDebounceTimer)
  }
  if (syncLeaderLeaseTimer !== null) {
    clearInterval(syncLeaderLeaseTimer)
  }
  stopSyncLeaderPoll()
  window.removeEventListener('storage', onStorageChanged)
})
</script>

<template>
  <NavBar
    :admin-mode="adminMode"
    :read-only="readOnly"
    :eng-dirty="engDirty"
    :ent-status="entStatus"
    @open-save-dialog="saveDialogMode = $event"
  />

  <output
    v-if="adminMode"
    class="admin-banner"
  >
    <strong>Admin mode</strong> — writes to both repositories are permitted.
    Use the <strong>Save</strong> and <strong>Submit</strong> controls in the Global nav to commit and submit enterprise changes.
  </output>

  <output
    v-if="readOnly"
    class="readonly-banner"
  >
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
