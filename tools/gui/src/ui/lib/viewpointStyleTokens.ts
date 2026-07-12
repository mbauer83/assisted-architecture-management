/**
 * Token-to-visual mapping convention for viewpoint style capabilities (companion plan
 * §5.2). `StyleRule.value`/`RangeBand.value` are opaque tokens drawn from the fixed
 * `STYLE_TOKENS` vocabulary (`viewpointPresentation.ts`) — domain code never interprets
 * them. This is the first surface adapter to resolve that vocabulary to a concrete
 * visual per capability (WU-E8); every other surface (table badges, matrix cell
 * emphasis, diagram overlay) reuses the same mapping so a token means the same thing
 * everywhere.
 */

export type StyleToken = 'emphasis' | 'positive' | 'caution' | 'critical' | 'neutral'

const TOKEN_COLORS: Record<StyleToken, string> = {
  emphasis: '#2563eb',
  positive: '#16a34a',
  caution: '#d97706',
  critical: '#dc2626',
  neutral: '#6b7280',
}

/** `node_color` / `edge_color` / `cluster_grouping`: a solid color swatch. */
export const tokenColor = (token: string): string => TOKEN_COLORS[token as StyleToken] ?? TOKEN_COLORS.neutral

const TOKEN_SHAPES: Record<StyleToken, 'circle' | 'diamond' | 'triangle' | 'square'> = {
  emphasis: 'circle',
  positive: 'circle',
  caution: 'diamond',
  critical: 'triangle',
  neutral: 'square',
}

/** `node_shape`: the fixed-notation exploration node outline. */
export const tokenShape = (token: string): 'circle' | 'diamond' | 'triangle' | 'square' =>
  TOKEN_SHAPES[token as StyleToken] ?? TOKEN_SHAPES.neutral

const TOKEN_ICON_LETTERS: Record<StyleToken, string> = {
  emphasis: 'E', positive: '+', caution: '!', critical: '×', neutral: '·',
}

/** `node_icon`: a small corner-badge glyph (no icon font dependency). */
export const tokenIconLetter = (token: string): string => TOKEN_ICON_LETTERS[token as StyleToken] ?? '·'

export interface EdgeEmphasisStyle {
  readonly strokeWidth: number
  readonly dashArray: string | undefined
}

const TOKEN_EDGE_EMPHASIS: Record<StyleToken, EdgeEmphasisStyle> = {
  emphasis: { strokeWidth: 3, dashArray: undefined },
  positive: { strokeWidth: 2, dashArray: undefined },
  caution: { strokeWidth: 2.5, dashArray: '6 3' },
  critical: { strokeWidth: 4, dashArray: undefined },
  neutral: { strokeWidth: 1.5, dashArray: '2 3' },
}

/** `edge_emphasis`: stroke width + dash pattern. */
export const tokenEdgeEmphasis = (token: string): EdgeEmphasisStyle =>
  TOKEN_EDGE_EMPHASIS[token as StyleToken] ?? TOKEN_EDGE_EMPHASIS.neutral

export const STYLE_TOKEN_LABELS: Record<StyleToken, string> = {
  emphasis: 'Emphasis', positive: 'Positive', caution: 'Caution', critical: 'Critical', neutral: 'Neutral',
}

export const tokenLabel = (token: string): string => STYLE_TOKEN_LABELS[token as StyleToken] ?? token
