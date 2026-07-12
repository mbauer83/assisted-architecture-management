/**
 * Builder tree <-> canonical wire mapping conversion — the exact counterpart of
 * `src/domain/viewpoint_criteria_serialization.py` / `viewpoint_criteria_parsing.py`: same
 * omit-defaults-on-write rules, same discriminated `kind` dispatch. `parse ∘ serialize`
 * must be the identity on every valid tree, verified by `viewpointCriteriaSerialization.test.ts`.
 */

import {
  type Comparator,
  type ConditionNode, type Conjunction,
  type ConnectionSelectionNode,
  type CriteriaNode,
  type ExecutableQueryNode,
  type GroupKind,
  type GroupNode,
  type IncidentDirection,
  type IncidentNode,
  type NeighborInclusionNode,
  type ValueRef,
  endpointValue,
  literalValue,
  mkGroup,
  mkQuery,
  nextNodeId,
  selfValue,
} from './viewpointCriteria'

// ── to mapping ────────────────────────────────────────────────────────────────

const valueRefToRaw = (value: ValueRef): unknown => {
  if (value.kind === 'literal') return value.literal
  const from = value.kind === 'self' ? 'self' : value.kind
  return { from, attribute: value.attribute }
}

/** Mirrors `ValueRef()`'s default (`kind="literal", literal=None`) — the wire shape a
 * condition's absent `value` key parses to (`_value_ref_from_raw(raw.get("value"))` with
 * no key present). Distinct from `mkCondition`'s UI-ergonomic starting value (`''`, a
 * blank text field) — this is only the *parse* default used for the omit-on-write check. */
const isUnsetValue = (value: ValueRef): boolean => value.kind === 'literal' && value.literal === null

const conditionToMapping = (node: ConditionNode): Record<string, unknown> => {
  const result: Record<string, unknown> = { kind: 'condition', attribute: node.attribute, comparator: node.comparator }
  if (!isUnsetValue(node.value)) result.value = valueRefToRaw(node.value)
  if (node.negate) result.negate = true
  return result
}

const incidentToMapping = (node: IncidentNode): Record<string, unknown> => {
  const result: Record<string, unknown> = { kind: 'incident' }
  if (node.direction !== 'either') result.direction = node.direction
  if (node.connectionCriteria !== null) result.connection_criteria = groupToMapping(node.connectionCriteria)
  if (node.endpointCriteria !== null) result.endpoint_criteria = groupToMapping(node.endpointCriteria)
  if (node.negate) result.negate = true
  return result
}

const criteriaNodeToMapping = (node: CriteriaNode): Record<string, unknown> => {
  if (node.kind === 'condition') return conditionToMapping(node)
  if (node.kind === 'incident') return incidentToMapping(node)
  return groupToMapping(node)
}

export const groupToMapping = (group: GroupNode): Record<string, unknown> => {
  const result: Record<string, unknown> = {
    kind: 'group', conjunction: group.conjunction, children: group.children.map(criteriaNodeToMapping),
  }
  if (group.negate) result.negate = true
  return result
}

export const neighborInclusionToMapping = (inclusion: NeighborInclusionNode): Record<string, unknown> => {
  const result: Record<string, unknown> = {}
  if (inclusion.direction !== 'either') result.direction = inclusion.direction
  if (inclusion.connectionCriteria !== null) result.connection_criteria = groupToMapping(inclusion.connectionCriteria)
  if (inclusion.neighborCriteria !== null) result.neighbor_criteria = groupToMapping(inclusion.neighborCriteria)
  return result
}

const isDefaultConnectionGroup = (group: GroupNode): boolean =>
  group.conjunction === 'and' && !group.negate && group.children.length === 0

export const connectionSelectionToMapping = (selection: ConnectionSelectionNode): Record<string, unknown> => {
  const result: Record<string, unknown> = {}
  if (!selection.enabled) result.enabled = false
  if (!isDefaultConnectionGroup(selection.criteria)) result.criteria = groupToMapping(selection.criteria)
  return result
}

// ── from mapping ──────────────────────────────────────────────────────────────

const valueRefFromRaw = (raw: unknown): ValueRef => {
  if (raw !== null && typeof raw === 'object' && 'from' in (raw as Record<string, unknown>)) {
    const from = String((raw as Record<string, unknown>).from)
    const attribute = String((raw as Record<string, unknown>).attribute)
    return from === 'self' ? selfValue(attribute) : endpointValue(from as 'source' | 'target', attribute)
  }
  return literalValue(raw ?? null)
}

const asRecord = (raw: unknown): Record<string, unknown> => raw as Record<string, unknown>

const conditionFromMapping = (raw: Record<string, unknown>): ConditionNode => ({
  kind: 'condition', id: nextNodeId(),
  attribute: String(raw.attribute), comparator: raw.comparator as Comparator,
  value: valueRefFromRaw(raw.value), negate: Boolean(raw.negate ?? false),
})

const incidentFromMapping = (raw: Record<string, unknown>): IncidentNode => ({
  kind: 'incident', id: nextNodeId(),
  direction: (raw.direction as IncidentDirection) ?? 'either',
  negate: Boolean(raw.negate ?? false),
  connectionCriteria: raw.connection_criteria != null ? groupFromMapping(asRecord(raw.connection_criteria), 'connection') : null,
  endpointCriteria: raw.endpoint_criteria != null ? groupFromMapping(asRecord(raw.endpoint_criteria), 'entity') : null,
})

const criteriaNodeFromMapping = (raw: Record<string, unknown>, groupKind: GroupKind): CriteriaNode => {
  if (raw.kind === 'condition') return conditionFromMapping(raw)
  if (raw.kind === 'incident' && groupKind === 'entity') return incidentFromMapping(raw)
  if (raw.kind === 'group') return groupFromMapping(raw, groupKind)
  throw new Error(`unknown criteria node kind ${String(raw.kind)}`)
}

export const groupFromMapping = (raw: Record<string, unknown>, groupKind: GroupKind): GroupNode => {
  const children = Array.isArray(raw.children) ? raw.children : []
  const node = mkGroup(groupKind, (raw.conjunction as Conjunction) ?? 'and')
  node.negate = Boolean(raw.negate ?? false)
  node.children = children.map((child) => criteriaNodeFromMapping(asRecord(child), groupKind))
  return node
}

export const neighborInclusionFromMapping = (raw: Record<string, unknown>): NeighborInclusionNode => ({
  id: nextNodeId(),
  direction: (raw.direction as IncidentDirection) ?? 'either',
  connectionCriteria: raw.connection_criteria != null ? groupFromMapping(asRecord(raw.connection_criteria), 'connection') : null,
  neighborCriteria: raw.neighbor_criteria != null ? groupFromMapping(asRecord(raw.neighbor_criteria), 'entity') : null,
})

export const connectionSelectionFromMapping = (raw: unknown): ConnectionSelectionNode => {
  if (raw == null) return { enabled: true, criteria: mkGroup('connection') }
  const rec = asRecord(raw)
  return {
    enabled: Boolean(rec.enabled ?? true),
    criteria: rec.criteria != null ? groupFromMapping(asRecord(rec.criteria), 'connection') : mkGroup('connection'),
  }
}

export const queryToMapping = (query: ExecutableQueryNode): Record<string, unknown> => {
  const result: Record<string, unknown> = {
    query_schema: query.querySchema,
    entity_criteria: groupToMapping(query.entityCriteria),
  }
  if (query.includeConnected.length > 0) {
    result.include_connected = query.includeConnected.map(neighborInclusionToMapping)
  }
  const connections = connectionSelectionToMapping(query.connections)
  if (Object.keys(connections).length > 0) result.connections = connections
  return result
}

export const queryFromMapping = (raw: unknown): ExecutableQueryNode => {
  const query = mkQuery()
  if (raw == null) return query
  const rec = asRecord(raw)
  query.entityCriteria = rec.entity_criteria != null ? groupFromMapping(asRecord(rec.entity_criteria), 'entity') : mkGroup('entity')
  query.includeConnected = Array.isArray(rec.include_connected)
    ? rec.include_connected.map((i) => neighborInclusionFromMapping(asRecord(i)))
    : []
  query.connections = connectionSelectionFromMapping(rec.connections)
  return query
}
