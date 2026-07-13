import { Schema } from 'effect'

export const EngagementSyncStatusSchema = Schema.Struct({
  has_uncommitted_changes: Schema.Boolean,
})
export type EngagementSyncStatus = typeof EngagementSyncStatusSchema.Type

export const EnterpriseSyncStatusSchema = Schema.Struct({
  status: Schema.String,
  label: Schema.String,
  branch: Schema.NullOr(Schema.String),
  branch_tip: Schema.NullOr(Schema.String),
  pushed_at: Schema.NullOr(Schema.String),
  commits_behind: Schema.NullOr(Schema.Number),
  commits_ahead: Schema.optional(Schema.Number),
  has_uncommitted_changes: Schema.Boolean,
})
export type EnterpriseSyncStatus = typeof EnterpriseSyncStatusSchema.Type

export const SyncStatusSchema = Schema.Struct({
  engagement: Schema.NullOr(EngagementSyncStatusSchema),
  enterprise: Schema.NullOr(EnterpriseSyncStatusSchema),
})
export type SyncStatus = typeof SyncStatusSchema.Type

export const SyncSaveResultSchema = Schema.Struct({
  ok: Schema.Boolean,
  commit: Schema.optional(Schema.String),
  pushed: Schema.optional(Schema.Boolean),
  message: Schema.optional(Schema.String),
  branch: Schema.optional(Schema.String),
  discarded_branch: Schema.optional(Schema.String),
  already_submitted: Schema.optional(Schema.Boolean),
  nothing_to_discard: Schema.optional(Schema.Boolean),
})
export type SyncSaveResult = typeof SyncSaveResultSchema.Type
