import { describe, expect, it } from 'vitest'
import { definitionFromMapping } from './viewpointDefinitionSerialization'
import { resolveIssuePathNodeId } from './viewpointIssuePath'

const EXAMPLE = {
  slug: 'components-serving-processes', version: 2, name: 'Components Serving Processes',
  query: {
    query_schema: 1,
    entity_criteria: {
      kind: 'group', conjunction: 'and',
      children: [
        { kind: 'condition', attribute: 'type', comparator: 'eq', value: 'application-component' },
        {
          kind: 'incident', direction: 'outgoing',
          connection_criteria: {
            kind: 'group', conjunction: 'and',
            children: [{ kind: 'condition', attribute: 'type', comparator: 'eq', value: 'archimate-serving' }],
          },
          endpoint_criteria: {
            kind: 'group', conjunction: 'and',
            children: [{ kind: 'condition', attribute: 'type', comparator: 'eq', value: 'process' }],
          },
        },
      ],
    },
    include_connected: [
      {
        direction: 'outgoing',
        neighbor_criteria: { kind: 'group', conjunction: 'and', children: [{ kind: 'condition', attribute: 'type', comparator: 'eq', value: 'process' }] },
      },
    ],
  },
  presentation: {
    representation: 'table',
    styling_rules: [
      { capability: 'badges', mode: 'match', match_criteria: { kind: 'group', conjunction: 'and', children: [{ kind: 'condition', attribute: 'status', comparator: 'eq', value: 'deprecated' }] } },
    ],
  },
}

describe('resolveIssuePathNodeId', () => {
  const draft = definitionFromMapping(EXAMPLE)

  it('resolves a leaf field on the top-level entity_criteria to its group node', () => {
    const id = resolveIssuePathNodeId('/query/entity_criteria/attribute', draft)
    expect(id).toBe(draft.query!.entityCriteria.id)
  })

  it('resolves a condition nested inside the root group by index', () => {
    const conditionNode = draft.query!.entityCriteria.children[0]
    const id = resolveIssuePathNodeId('/query/entity_criteria/children/0/attribute', draft)
    expect(id).toBe(conditionNode.id)
  })

  it('resolves into an incident condition leg (endpoint_criteria)', () => {
    const incident = draft.query!.entityCriteria.children[1]
    if (incident.kind !== 'incident') throw new Error('expected incident')
    const id = resolveIssuePathNodeId('/query/entity_criteria/children/1/endpoint_criteria/children/0/attribute', draft)
    expect(id).toBe(incident.endpointCriteria!.children[0].id)
  })

  it('resolves into a neighbor inclusion by list index', () => {
    const inclusion = draft.query!.includeConnected[0]
    const id = resolveIssuePathNodeId('/query/include_connected/0/direction', draft)
    expect(id).toBe(inclusion.id)
  })

  it('resolves into a styling rule match_criteria condition', () => {
    const rule = draft.presentation!.stylingRules[0]
    const id = resolveIssuePathNodeId('/presentation/styling_rules/0/match_criteria/children/0/comparator', draft)
    expect(id).toBe(rule.matchCriteria!.children[0].id)
  })

  it('returns null for a top-level leaf field with no builder node', () => {
    expect(resolveIssuePathNodeId('/slug', draft)).toBeNull()
    expect(resolveIssuePathNodeId('/version', draft)).toBeNull()
  })
})
