import { Schema } from 'effect'

export const PermittedConnectionsByPeerSchema = Schema.Struct({
  outgoing: Schema.Record({ key: Schema.String, value: Schema.Array(Schema.String) }),
  incoming: Schema.Record({ key: Schema.String, value: Schema.Array(Schema.String) }),
  symmetric: Schema.Record({ key: Schema.String, value: Schema.Array(Schema.String) }),
})

export const SpecializationGuidanceSchema = Schema.Struct({
  slug: Schema.String,
  name: Schema.String,
  description: Schema.String,
  create_when: Schema.String,
  never_create_when: Schema.String,
  notation: Schema.optional(Schema.Struct({
    icon: Schema.optional(Schema.String),
    color: Schema.optional(Schema.String),
  })),
})
export type SpecializationGuidance = typeof SpecializationGuidanceSchema.Type

export const GuidanceContextLayerSchema = Schema.Struct({
  level: Schema.String,
  node: Schema.String,
  text: Schema.String,
})

export const EntityTypeGuidanceSchema = Schema.Struct({
  name: Schema.String,
  prefix: Schema.String,
  domain: Schema.optional(Schema.String),
  classes: Schema.Array(Schema.String),
  create_when: Schema.String,
  never_create_when: Schema.String,
  permitted_connections: PermittedConnectionsByPeerSchema,
  specializations: Schema.optional(Schema.Array(SpecializationGuidanceSchema)),
  // v2 layered guidance: composed ancestry context, broadest first. Absent when none.
  context: Schema.optional(Schema.Array(GuidanceContextLayerSchema)),
})
export type EntityTypeGuidance = typeof EntityTypeGuidanceSchema.Type

export const ConnectionTypeGuidanceSchema = Schema.Struct({
  name: Schema.String,
  specializations: Schema.Array(SpecializationGuidanceSchema),
})
export type ConnectionTypeGuidance = typeof ConnectionTypeGuidanceSchema.Type

export const PairGuidanceSchema = Schema.Struct({
  source: Schema.optional(Schema.String),
  target: Schema.optional(Schema.String),
  outgoing: Schema.optional(Schema.Array(Schema.String)),
  incoming: Schema.optional(Schema.Array(Schema.String)),
  symmetric: Schema.optional(Schema.Array(Schema.String)),
  error: Schema.optional(Schema.String),
  known_types: Schema.optional(Schema.Array(Schema.String)),
})
export type PairGuidance = typeof PairGuidanceSchema.Type

export const AuthoringGuidanceSchema = Schema.Struct({
  entity_types: Schema.optional(Schema.Array(EntityTypeGuidanceSchema)),
  connection_types: Schema.optional(Schema.Array(ConnectionTypeGuidanceSchema)),
  total: Schema.optional(Schema.Number),
  domains: Schema.optional(Schema.Array(Schema.String)),
  pair_guidance: Schema.optional(PairGuidanceSchema),
  diagram_type_guidance: Schema.optional(Schema.Unknown),
  error: Schema.optional(Schema.String),
  unknown: Schema.optional(Schema.Array(Schema.String)),
  guidance_status: Schema.optional(Schema.Literal("empty")),
  guidance_hint: Schema.optional(Schema.String),
})
export type AuthoringGuidance = typeof AuthoringGuidanceSchema.Type
