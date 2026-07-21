/**
 * Pure logic for the ontology-driven edge picker: the served edge catalog is
 * the ONLY source of offered connection types (no literal list exists in the
 * frontend), filtered to the legal set for the concrete (source, target)
 * node-type pair in the chosen direction.
 */

export interface EdgeCatalogRow {
  source_type: string
  target_type: string
  connection_types: string[]
}

export interface EdgeCatalog {
  edge_types: { name: string; label: string }[]
  permitted: EdgeCatalogRow[]
  reference_types: { name: string; description: string }[]
}

export type EdgeDirection = 'outgoing' | 'incoming'

export const legalTypesForPair = (
  catalog: EdgeCatalog,
  sourceType: string,
  targetType: string,
): string[] => {
  const row = catalog.permitted.find(
    (r) => r.source_type === sourceType && r.target_type === targetType,
  )
  return row ? [...row.connection_types] : []
}

/** The legal set for the picker's current selection: for an incoming edge the
 * searched node is the SOURCE and the panel's node the target. */
export const legalTypesForSelection = (
  catalog: EdgeCatalog,
  direction: EdgeDirection,
  panelNodeType: string,
  otherNodeType: string,
): string[] =>
  direction === 'outgoing'
    ? legalTypesForPair(catalog, panelNodeType, otherNodeType)
    : legalTypesForPair(catalog, otherNodeType, panelNodeType)

export const emptyLegalSetMessage = (
  direction: EdgeDirection,
  panelNodeType: string,
  otherNodeType: string,
): string => {
  const [from, to] = direction === 'outgoing'
    ? [panelNodeType, otherNodeType]
    : [otherNodeType, panelNodeType]
  return `No edge type is legal from ${from} to ${to}. `
    + 'Architecture references (e.g. evidence bindings) go through the arch-reference form instead.'
}

/** Source/target ids for submission, honoring the direction. */
export const edgeSubmission = (
  direction: EdgeDirection,
  panelNodeId: string,
  otherNodeId: string,
  connType: string,
): { source_id: string; target_id: string; conn_type: string } =>
  direction === 'outgoing'
    ? { source_id: panelNodeId, target_id: otherNodeId, conn_type: connType }
    : { source_id: otherNodeId, target_id: panelNodeId, conn_type: connType }
