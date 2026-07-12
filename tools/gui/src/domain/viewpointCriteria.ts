/**
 * The criteria-tree builder's working model: one recursive tree shape reused for query
 * filtering, neighbor inclusion, style-rule match mode, and matrix axis criteria — mirrors
 * `src/domain/viewpoint_criteria.py` field for field. Each node carries a UI-only `id`
 * (never serialized) so Vue can key/target individual nodes; `viewpointCriteriaSerialization.ts`
 * is the counterpart that converts to/from the canonical wire mapping.
 */

let uidCounter = 0
export const nextNodeId = (): string => `n${++uidCounter}`

export type Conjunction = 'and' | 'or'
export type Comparator = 'eq' | 'neq' | 'in' | 'exists' | 'absent' | 'lt' | 'lte' | 'gt' | 'gte'
export type IncidentDirection = 'outgoing' | 'incoming' | 'either'
export type GroupKind = 'entity' | 'connection'
export type ValueRefKind = 'literal' | 'self' | 'source' | 'target'

export const NUMERIC_COMPARATORS: readonly Comparator[] = ['lt', 'lte', 'gt', 'gte']
export const RESERVED_ENTITY_PATHS: readonly string[] = [
  'id', 'name', 'type', 'specialization', 'group', 'domain', 'subdomain', 'status', 'version',
]
export const RESERVED_CONNECTION_PATHS: readonly string[] = ['id', 'type', 'specialization']

export interface ValueRefLiteral {
  readonly kind: 'literal'
  readonly literal: unknown
}
export interface ValueRefAttribute {
  readonly kind: 'self' | 'source' | 'target'
  readonly attribute: string
}
export type ValueRef = ValueRefLiteral | ValueRefAttribute

export const literalValue = (literal: unknown): ValueRef => ({ kind: 'literal', literal })
export const selfValue = (attribute: string): ValueRef => ({ kind: 'self', attribute })
export const endpointValue = (endpoint: 'source' | 'target', attribute: string): ValueRef => ({
  kind: endpoint, attribute,
})

export interface ConditionNode {
  readonly kind: 'condition'
  readonly id: string
  attribute: string
  comparator: Comparator
  value: ValueRef
  negate: boolean
}

export interface IncidentNode {
  readonly kind: 'incident'
  readonly id: string
  direction: IncidentDirection
  negate: boolean
  connectionCriteria: GroupNode | null
  endpointCriteria: GroupNode | null
}

export interface GroupNode {
  readonly kind: 'group'
  readonly id: string
  readonly groupKind: GroupKind
  conjunction: Conjunction
  negate: boolean
  children: CriteriaNode[]
}

export type CriteriaNode = ConditionNode | IncidentNode | GroupNode

export const mkCondition = (attribute = 'type', comparator: Comparator = 'eq'): ConditionNode => ({
  kind: 'condition', id: nextNodeId(), attribute, comparator, value: literalValue(''), negate: false,
})

export const mkGroup = (groupKind: GroupKind, conjunction: Conjunction = 'and'): GroupNode => ({
  kind: 'group', id: nextNodeId(), groupKind, conjunction, negate: false, children: [],
})

export const mkIncident = (): IncidentNode => ({
  kind: 'incident', id: nextNodeId(), direction: 'either', negate: false,
  connectionCriteria: mkGroup('connection'), endpointCriteria: mkGroup('entity'),
})

export interface NeighborInclusionNode {
  readonly id: string
  direction: IncidentDirection
  connectionCriteria: GroupNode | null
  neighborCriteria: GroupNode | null
}

export const mkNeighborInclusion = (): NeighborInclusionNode => ({
  id: nextNodeId(), direction: 'either', connectionCriteria: mkGroup('connection'), neighborCriteria: mkGroup('entity'),
})

export interface ConnectionSelectionNode {
  enabled: boolean
  criteria: GroupNode
}

export const mkConnectionSelection = (): ConnectionSelectionNode => ({ enabled: true, criteria: mkGroup('connection') })

export interface ExecutableQueryNode {
  querySchema: number
  entityCriteria: GroupNode
  includeConnected: NeighborInclusionNode[]
  connections: ConnectionSelectionNode
}

export const QUERY_SCHEMA_VERSION = 2

export const mkQuery = (): ExecutableQueryNode => ({
  querySchema: QUERY_SCHEMA_VERSION,
  entityCriteria: mkGroup('entity'),
  includeConnected: [],
  connections: mkConnectionSelection(),
})
