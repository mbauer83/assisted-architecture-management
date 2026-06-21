export interface AssuranceDiagramNode {
  node_id: string
  node_type: string
  name: string
  uca_type?: string
}

export interface AssuranceDiagramEdge {
  edge_id?: string
  source_id: string
  target_id: string
  conn_type: string
  label?: string
  name?: string
}

export const UCA_TYPES = [
  'not-provided',
  'provided',
  'wrong-timing',
  'stopped-too-soon',
] as const

export interface UcaMatrixRow {
  controlAction: AssuranceDiagramNode
  cells: Record<string, AssuranceDiagramNode[]>
}

export function assuranceNodeAlias(nodeId: string): string {
  return `N_${nodeId.replace(/[@.-]/g, '_')}`
}

export function buildAssuranceAliasMap(
  nodes: ReadonlyArray<AssuranceDiagramNode>,
): Map<string, string> {
  return new Map(nodes.map((node) => [assuranceNodeAlias(node.node_id), node.node_id]))
}

export function buildUcaMatrixRows(
  nodes: ReadonlyArray<AssuranceDiagramNode>,
  edges: ReadonlyArray<AssuranceDiagramEdge>,
): UcaMatrixRow[] {
  const actions = nodes.filter((node) => node.node_type === 'control-action')
  const ucas = new Map(
    nodes
      .filter((node) => node.node_type === 'unsafe-control-action')
      .map((node) => [node.node_id, node]),
  )
  const actionById = new Map(actions.map((node) => [node.node_id, node]))
  const cellsByAction = new Map<string, Record<string, AssuranceDiagramNode[]>>()
  for (const edge of edges) {
    if (edge.conn_type !== 'concerns') continue
    const uca = ucas.get(edge.source_id)
    if (!uca || !actionById.has(edge.target_id)) continue
    const cells = cellsByAction.get(edge.target_id) ?? {}
    const key = uca.uca_type || 'unspecified'
    ;(cells[key] ??= []).push(uca)
    cellsByAction.set(edge.target_id, cells)
  }
  return actions.map((controlAction) => ({
    controlAction,
    cells: cellsByAction.get(controlAction.node_id) ?? {},
  }))
}
