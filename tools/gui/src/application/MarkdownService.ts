import { Effect } from 'effect'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { artifactRouteForHref } from '../domain/artifactLinks'

export class MarkdownError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'MarkdownError'
  }
}

// Repository-relative artifact links would otherwise resolve against the current
// GUI route and 404 — rewrite them to their in-app routes at token level, before
// rendering. Registered once, on the shared marked instance.
marked.use({
  walkTokens: (token) => {
    if (token.type === 'link' && typeof token.href === 'string') {
      const route = artifactRouteForHref(token.href)
      if (route !== null) token.href = route
    }
  },
})

/** Render markdown to sanitized HTML with artifact links mapped to in-app routes. */
export const renderMarkdown = (content: string): string =>
  DOMPurify.sanitize(marked.parse(content, { async: false }))

/**
 * An Effect that takes a string and returns sanitized HTML.
 */
export const parseMarkdown = (content: string) =>
  Effect.try({
    try: () => renderMarkdown(content),
    catch: (error) => new MarkdownError(`Markdown rendering failed: ${String(error)}`),
  })
