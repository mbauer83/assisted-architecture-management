/**
 * Presentation builder model: representation, style rules (match/range), columns, and
 * matrix axes — mirrors `PresentationSpec`/`StyleRule`/`RangeBand`/`ColumnSpec` in
 * `src/domain/viewpoints.py`. See `viewpointCriteria.ts` for the criteria-tree types
 * style-rule `mode="match"` criteria and matrix criteria-axes reuse unmodified.
 */

import { type GroupNode, mkGroup, nextNodeId } from './viewpointCriteria'

export type Representation = 'exploration' | 'table' | 'matrix' | 'diagram'
export type StyleMode = 'match' | 'range' | 'scale'

export const REPRESENTATION_CAPABILITIES: Readonly<Record<Representation, readonly string[]>> = {
  exploration: ['node_shape', 'node_icon', 'node_color', 'edge_color', 'edge_emphasis', 'cluster_grouping'],
  table: ['columns', 'badges', 'sort', 'row_grouping'],
  matrix: ['row_by', 'column_by', 'cell_emphasis'],
  diagram: ['node_color', 'edge_color', 'edge_emphasis', 'cluster_grouping'],
}

/** GUI-only convention — the domain treats `StyleRule.value` as a freeform opaque string
 * (a surface adapter resolves it to a shape/icon/color per capability); this is the fixed
 * token vocabulary the signed-off wireframe standardized the picker on. */
export const STYLE_TOKENS: readonly string[] = ['emphasis', 'positive', 'caution', 'critical', 'neutral']

export const GROUP_BY_DIMENSIONS: readonly string[] = ['type', 'specialization', 'group']

export interface RangeBandNode {
  readonly id: string
  minimum: number | null
  maximum: number | null
  value: string
}

export const mkRangeBand = (): RangeBandNode => ({ id: nextNodeId(), minimum: null, maximum: null, value: STYLE_TOKENS[0] })

export interface StyleRuleNode {
  readonly id: string
  capability: string
  appliesTo: string[]
  mode: StyleMode
  matchCriteria: GroupNode | null
  rangeAttribute: string | null
  rangeBands: RangeBandNode[]
  value: string | null
  /** `mode === 'scale'`: the numeric/date attribute path driving a continuous
   * interpolation, its bounds (`null` = data-driven), and its two gradient-endpoint
   * tokens — an author-chosen opaque pair, not restricted to `STYLE_TOKENS`. */
  scaleAttribute: string | null
  scaleMin: number | string | null
  scaleMax: number | string | null
  scaleTokens: readonly [string, string] | null
}

/** An `edge_*` capability's `match_criteria` is connection criteria; every other
 * capability (including matrix's `cell_emphasis`) takes entity criteria. */
export const isEdgeCapability = (capability: string): boolean => capability.startsWith('edge_')

export const mkStyleRule = (representation: Representation): StyleRuleNode => {
  const capability = REPRESENTATION_CAPABILITIES[representation][0]
  return {
    id: nextNodeId(), capability, appliesTo: [], mode: 'match',
    matchCriteria: mkGroup(isEdgeCapability(capability) ? 'connection' : 'entity'),
    rangeAttribute: null, rangeBands: [], value: STYLE_TOKENS[0],
    scaleAttribute: null, scaleMin: null, scaleMax: null, scaleTokens: null,
  }
}

export interface ColumnSpecNode {
  readonly id: string
  label: string
  source: string
}

export const mkColumn = (): ColumnSpecNode => ({ id: nextNodeId(), label: '', source: 'name' })

export type MatrixAxisMode = 'grouped' | 'criteria'

export interface PresentationNode {
  representation: Representation
  displayOptions: Record<string, unknown>
  columns: ColumnSpecNode[] | null
  rowBy: string | null
  columnBy: string | null
  rowCriteria: GroupNode | null
  columnCriteria: GroupNode | null
  groupBy: string | null
  stylingRules: StyleRuleNode[]
  defaultStyle: Record<string, string>
}

export const mkPresentation = (representation: Representation): PresentationNode => ({
  representation, displayOptions: {}, columns: representation === 'table' ? [] : null,
  rowBy: null, columnBy: null, rowCriteria: null, columnCriteria: null, groupBy: null,
  stylingRules: [], defaultStyle: {},
})

export const matrixAxisMode = (presentation: PresentationNode): MatrixAxisMode | null => {
  if (presentation.rowBy !== null || presentation.columnBy !== null) return 'grouped'
  if (presentation.rowCriteria !== null || presentation.columnCriteria !== null) return 'criteria'
  return null
}
