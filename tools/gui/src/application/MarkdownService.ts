import { Effect } from 'effect'
import DOMPurify from 'dompurify'
import { marked } from 'marked'

export class MarkdownError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'MarkdownError'
  }
}

/**
 * An Effect that takes a string and returns sanitized HTML.
 */
export const parseMarkdown = (content: string) =>
  // Effect.tryPromise handles the async nature of marked.parse
  Effect.tryPromise({
    try: async () => {
      const rawHtml = await marked.parse(content)
      return DOMPurify.sanitize(rawHtml)
    },
    catch: (error) => new MarkdownError(`Markdown rendering failed: ${String(error)}`),
  })
