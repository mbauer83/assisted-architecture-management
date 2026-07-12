import { describe, expect, it } from 'vitest'
import { definitionFromMapping, definitionToMapping } from './viewpointDefinitionSerialization'

// Same five example definitions exercised by tests/domain/test_viewpoint_appendix_a_examples.py
// (verbatim from tests/fixtures/viewpoints/appendix_a_examples.yaml) — one canonical wire
// mapping shared by both the Python and TypeScript parsers/serializers.
const CANONICAL_EXAMPLES: Record<string, unknown>[] = [
  {
    slug: 'application-components', version: 1, name: 'Application Components',
    purpose: 'informing', content: 'overview',
    query: {
      query_schema: 2,
      entity_criteria: {
        kind: 'group', conjunction: 'and',
        children: [{ kind: 'condition', attribute: 'type', comparator: 'in', value: ['application-component'] }],
      },
    },
  },
  {
    slug: 'active-app-tech', version: 1, name: 'Active Application & Technology',
    query: {
      query_schema: 2,
      entity_criteria: {
        kind: 'group', conjunction: 'and',
        children: [
          {
            kind: 'group', conjunction: 'or',
            children: [
              { kind: 'condition', attribute: 'domain', comparator: 'eq', value: 'application' },
              { kind: 'condition', attribute: 'domain', comparator: 'eq', value: 'technology' },
            ],
          },
          { kind: 'condition', attribute: 'status', comparator: 'eq', value: 'deprecated', negate: true },
        ],
      },
    },
  },
  {
    slug: 'components-serving-processes', version: 2, name: 'Components Serving Processes',
    query: {
      query_schema: 2,
      entity_criteria: {
        kind: 'group', conjunction: 'and',
        children: [
          { kind: 'condition', attribute: 'type', comparator: 'eq', value: 'application-component' },
          {
            kind: 'incident', direction: 'outgoing',
            connection_criteria: {
              kind: 'group', conjunction: 'and',
              children: [
                { kind: 'condition', attribute: 'type', comparator: 'eq', value: 'archimate-serving' },
                { kind: 'condition', attribute: 'strength', comparator: 'gte', value: 3 },
              ],
            },
            endpoint_criteria: {
              kind: 'group', conjunction: 'and',
              children: [
                { kind: 'condition', attribute: 'type', comparator: 'eq', value: 'process' },
                { kind: 'condition', attribute: 'specialization', comparator: 'eq', value: 'business-process' },
              ],
            },
          },
        ],
      },
      include_connected: [
        {
          direction: 'outgoing',
          connection_criteria: {
            kind: 'group', conjunction: 'and',
            children: [{ kind: 'condition', attribute: 'type', comparator: 'eq', value: 'archimate-serving' }],
          },
          neighbor_criteria: {
            kind: 'group', conjunction: 'and',
            children: [
              { kind: 'condition', attribute: 'type', comparator: 'eq', value: 'process' },
              { kind: 'condition', attribute: 'specialization', comparator: 'eq', value: 'business-process' },
            ],
          },
        },
      ],
      connections: {
        enabled: true,
        criteria: {
          kind: 'group', conjunction: 'and',
          children: [
            { kind: 'condition', attribute: 'type', comparator: 'eq', value: 'archimate-serving' },
            { kind: 'condition', attribute: 'strength', comparator: 'gte', value: { from: 'target', attribute: 'threshold' } },
          ],
        },
      },
    },
  },
  {
    slug: 'component-lifecycle-table', version: 1, name: 'Component Lifecycle',
    query: {
      query_schema: 2,
      entity_criteria: {
        kind: 'group', conjunction: 'and',
        children: [{ kind: 'condition', attribute: 'type', comparator: 'eq', value: 'application-component' }],
      },
    },
    presentation: {
      representation: 'table',
      columns: [
        { label: 'Name', source: 'name' },
        { label: 'Status', source: 'status' },
        { label: 'Risk', source: 'risk_score' },
      ],
      styling_rules: [
        {
          capability: 'badges', mode: 'match',
          match_criteria: {
            kind: 'group', conjunction: 'and',
            children: [{ kind: 'condition', attribute: 'status', comparator: 'eq', value: 'deprecated' }],
          },
          value: 'badge-warning',
        },
        {
          capability: 'badges', mode: 'range', range_attribute: 'risk_score',
          range_bands: [
            { minimum: null, maximum: 4, value: 'badge-ok' },
            { minimum: 4, maximum: 7, value: 'badge-caution' },
            { minimum: 7, maximum: null, value: 'badge-danger' },
          ],
        },
      ],
      default_style: { badges: 'badge-neutral' },
    },
  },
  {
    slug: 'requirement-coverage', version: 1, name: 'Requirement Coverage',
    query: {
      query_schema: 2,
      entity_criteria: { kind: 'group', conjunction: 'and', children: [] },
      connections: {
        enabled: true,
        criteria: {
          kind: 'group', conjunction: 'and',
          children: [{ kind: 'condition', attribute: 'type', comparator: 'eq', value: 'archimate-realization' }],
        },
      },
    },
    presentation: {
      representation: 'matrix',
      row_criteria: {
        kind: 'group', conjunction: 'and',
        children: [{ kind: 'condition', attribute: 'type', comparator: 'eq', value: 'requirement' }],
      },
      column_criteria: {
        kind: 'group', conjunction: 'and',
        children: [{ kind: 'condition', attribute: 'type', comparator: 'eq', value: 'application-component' }],
      },
    },
  },
]

describe('canonical example round-trip', () => {
  // Mirrors tests/domain/test_viewpoint_appendix_a_examples.py's own property: `parse` fills
  // in defaults the fixture omits (e.g. `purpose`/`content`, `connections.enabled: true`) and
  // `serialize` omits-on-write anything equal to a default, so the fixture's raw mapping and
  // its serialization legitimately differ. What must hold — and is id-noise-free, since a
  // builder node's `id` is UI-only and never survives serialization — is
  // `serialize(parse(serialize(parse(x)))) == serialize(parse(x))`: once through the wire
  // mapping and back is lossless.
  it.each(CANONICAL_EXAMPLES.map((example) => [example.slug as string, example] as const))(
    'wire mapping is stable across a second parse/serialize round-trip for %s',
    (_slug, example) => {
      const mapping = definitionToMapping(definitionFromMapping(example))
      const reMapping = definitionToMapping(definitionFromMapping(mapping))
      expect(reMapping).toEqual(mapping)
    },
  )
})
