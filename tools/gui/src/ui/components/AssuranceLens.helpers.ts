/**
 * Pure helper for AssuranceLens: process the raw arch-lens API response.
 * Extracted here so the stateless logic is testable without mounting the component.
 */

export interface LensNode {
  node_id: string
  node_type: string
  name: string
  tlp?: string
  status?: string
}

export interface LensResult {
  locked: boolean
  visible: boolean
  nodes: LensNode[]
  count: number
  visibilityLimited: boolean
}

export interface RawLensResponse {
  locked: boolean
  nodes: LensNode[]
  count: number
  visibility_limited?: boolean
}

/** Parse a raw lens API response into a typed, display-ready result. */
export function parseLensResponse(raw: RawLensResponse): LensResult {
  return {
    locked: raw.locked,
    visible: !raw.locked && raw.count > 0,
    nodes: raw.locked ? [] : raw.nodes,
    count: raw.locked ? 0 : raw.count,
    visibilityLimited: raw.visibility_limited ?? false,
  }
}

/** Build the assurance browse link for a given node. */
export function browseLinkForNode(nodeId: string): string {
  return `/assurance/browse?node_id=${encodeURIComponent(nodeId)}`
}
