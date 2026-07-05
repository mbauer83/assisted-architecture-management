import DOMPurify from 'dompurify'

/**
 * DOMPurify's default `ALLOWED_URI_REGEXP` only permits a fixed list of known-safe URI schemes
 * (http(s), mailto, tel, …) plus relative references; it silently strips `href`/`xlink:href`
 * for anything else, including our own `arch://<artifact-id>` sentinel links that renderers
 * emit so the viewer can map an SVG element back to its artifact (see the activity diagram
 * type's `[[arch://…]]` links). Extending the allow-list is DOMPurify's documented mechanism
 * for admitting an application-specific scheme without weakening the rest of its URL sanitizing.
 */
export const ALLOWED_URI_REGEXP = /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp|arch):|[^a-z]|[a-z+.-]+(?:[^a-z+.-:]|$))/i

export function sanitizeDiagramSvg(svg: string): string {
  return DOMPurify.sanitize(svg, {
    USE_PROFILES: { svg: true, svgFilters: true },
    ADD_ATTR: ['data-entity', 'data-entity-1', 'data-entity-2'],
    ALLOWED_URI_REGEXP,
  })
}
