import type { AuthoringGuidance, SpecializationGuidance } from '../../domain'

/**
 * Available specializations for one entity type, sourced from the `entity_types[].specializations`
 * block `artifact_authoring_guidance`/`GET /api/authoring-guidance` returns for that type — the
 * same guidance payload the create/edit forms already fetch for attribute schemas, so the picker
 * never needs its own round trip beyond a guidance call already scoped to the one type.
 */
export function specializationOptionsForEntityType(
  guidance: AuthoringGuidance | null,
  entityType: string,
): readonly SpecializationGuidance[] {
  if (!guidance?.entity_types) return []
  const entry = guidance.entity_types.find((e) => e.name === entityType)
  return entry?.specializations ?? []
}

/**
 * Available specializations for one connection type, sourced from the top-level
 * `connection_types` block — unlike entity types, connection types with no specializations are
 * omitted from that block entirely (see `_connection_type_guidance` in `type_guidance.py`), so
 * absence here means "none declared", not "not yet loaded".
 */
export function specializationOptionsForConnectionType(
  guidance: AuthoringGuidance | null,
  connectionType: string,
): readonly SpecializationGuidance[] {
  if (!guidance?.connection_types) return []
  const entry = guidance.connection_types.find((e) => e.name === connectionType)
  return entry?.specializations ?? []
}

/** Display label for a specialization option, e.g. for a `<select>`'s option text. */
export function specializationOptionLabel(spec: SpecializationGuidance): string {
  return spec.name || spec.slug
}
