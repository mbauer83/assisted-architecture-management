/**
 * Pure helpers for `CriteriaTreeBuilder.vue`: attribute/comparator/value-kind option lists
 * fed from the criteria-catalog registries snapshot, and the depth meter. Kept out of the
 * component so they're vitest-covered without mounting Vue.
 */

import type { InjectionKey, Ref } from 'vue'
import type { Comparator, GroupKind, ValueRefKind } from '../../domain/viewpointCriteria'
import { NUMERIC_COMPARATORS, RESERVED_CONNECTION_PATHS, RESERVED_ENTITY_PATHS } from '../../domain/viewpointCriteria'
import type { CriteriaCatalog } from '../../domain'

/** Provided by the management view, injected by every builder node so a save-time
 * validation issue can highlight the exact widget it names without prop-drilling a
 * highlight flag through every recursion level. */
export const HIGHLIGHTED_NODE_ID_KEY: InjectionKey<Ref<string | null>> = Symbol('highlightedNodeId')

export const DEPTH_CAP = 4

export interface AttributeOption {
  path: string
  reserved: boolean
  declaredType: string | null // null for reserved paths (no JSON-schema type)
}

/** One flat list: reserved read-model paths first, then effective-schema attributes — the
 * "one namespace, used everywhere a path appears" the evaluator itself assumes
 * (`RegistrySnapshot.entity_attribute_types` is flat across all entity types). */
export const attributeOptions = (groupKind: GroupKind, catalog: CriteriaCatalog): AttributeOption[] => {
  const reserved = groupKind === 'entity' ? RESERVED_ENTITY_PATHS : RESERVED_CONNECTION_PATHS
  const schemaTypes = groupKind === 'entity' ? catalog.entity_attribute_types : catalog.connection_attribute_types
  const reservedOptions = reserved.map((path) => ({ path, reserved: true, declaredType: null }))
  const schemaOptions = Object.keys(schemaTypes)
    .filter((path) => !reserved.includes(path))
    .sort()
    .map((path) => ({ path, reserved: false, declaredType: schemaTypes[path] }))
  return [...reservedOptions, ...schemaOptions]
}

const NUMERIC_TYPES = new Set(['integer', 'number', 'date'])

/** Reserved paths take string comparators only (none of them are numeric/date); a schema
 * attribute's numeric comparators gate on its declared type. */
export const comparatorsFor = (attribute: AttributeOption): readonly Comparator[] => {
  const allComparators: Comparator[] = ['eq', 'neq', 'in', 'exists', 'absent', 'lt', 'lte', 'gt', 'gte']
  const isNumeric = attribute.declaredType !== null && NUMERIC_TYPES.has(attribute.declaredType)
  return isNumeric ? allComparators : allComparators.filter((c) => !NUMERIC_COMPARATORS.includes(c))
}

/** Reserved paths with a real enumerable value set in the registries snapshot — anything
 * else (schema attributes, and reserved paths like `domain`/`status` the snapshot doesn't
 * enumerate) falls back to a free-text value input, never a fabricated choice list. */
export const enumChoicesFor = (attribute: string, groupKind: GroupKind, catalog: CriteriaCatalog): string[] | null => {
  if (attribute === 'type') return groupKind === 'entity' ? [...catalog.entity_types] : [...catalog.connection_types]
  if (attribute === 'specialization') return [...catalog.specialization_slugs]
  return null
}

export interface ValueKindOption {
  kind: ValueRefKind
  label: string
}

/** `attribute_of_endpoint` (source/target) is connection-condition-only: it reads an
 * attribute off the OTHER endpoint of the connection being evaluated — meaningless for an
 * entity condition, which has no endpoints. */
export const valueKindOptions = (groupKind: GroupKind): ValueKindOption[] => {
  const options: ValueKindOption[] = [
    { kind: 'literal', label: 'a fixed value' },
    { kind: 'self', label: `another attribute of this ${groupKind === 'connection' ? 'connection' : 'entity'}` },
  ]
  if (groupKind === 'connection') {
    options.push(
      { kind: 'source', label: "the source entity's attribute" },
      { kind: 'target', label: "the target entity's attribute" },
    )
  }
  return options
}

export const depthLabel = (depth: number): string => `nesting ${depth + 1} of ${DEPTH_CAP}`
export const atDepthCap = (depth: number): boolean => depth + 1 >= DEPTH_CAP
