/**
 * Repository-relative artifact hrefs → in-app routes.
 *
 * Document and entity markdown link to sibling artifacts with worktree-relative
 * hrefs (e.g. `../../../projects/x/model/motivation/requirement/REQ@….md`).
 * Rendered verbatim, the browser resolves those against the current GUI route
 * and lands on a page that does not exist. The artifact id is recoverable from
 * the filename, and the artifact kind from the repository area the path passes
 * through (`model/`, `docs/`, `diagram-catalog/`).
 */

const ARTIFACT_FILE = /^([A-Za-z]+@\d+\.[A-Za-z0-9_-]+\..+?)(\.outgoing)?\.(md|puml)$/

const hasScheme = (href: string): boolean => /^[a-z][a-z0-9+.-]*:/i.test(href) || href.startsWith('//')

/** Map an artifact-file href to its in-app route, or null when it is not one. */
export function artifactRouteForHref(href: string): string | null {
  if (href === '' || hasScheme(href) || href.startsWith('#')) return null
  const [pathOnly] = href.split(/[?#]/)
  const segments = pathOnly.split('/').filter((s) => s !== '' && s !== '.' && s !== '..')
  const last = segments.at(-1)
  if (last === undefined) return null
  const match = ARTIFACT_FILE.exec(safeDecode(last))
  if (!match) return null
  const id = match[1]
  if (segments.includes('model')) return `/entity?id=${encodeURIComponent(id)}`
  if (segments.includes('docs')) return `/documents/${encodeURIComponent(id)}`
  if (segments.includes('diagram-catalog')) return `/diagram?id=${encodeURIComponent(id)}`
  return null
}

const safeDecode = (segment: string): string => {
  try {
    return decodeURIComponent(segment)
  } catch {
    return segment
  }
}
