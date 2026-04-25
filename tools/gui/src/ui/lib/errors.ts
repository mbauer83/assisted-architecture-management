export const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null

export const readErrorMessage = (error: unknown): string => {
  if (error instanceof Error && error.message) {
    return error.message
  }
  if (typeof error === 'string') {
    return error
  }
  if (isRecord(error)) {
    const detail = error.detail
    if (typeof detail === 'string' && detail) {
      return detail
    }
    const message = error.message
    if (typeof message === 'string' && message) {
      try {
        const parsed = JSON.parse(message) as unknown
        if (isRecord(parsed) && typeof parsed.detail === 'string' && parsed.detail) {
          return parsed.detail
        }
      } catch {
        return message
      }
      return message
    }
  }
  return String(error)
}

export const collectVerificationIssues = (verification: unknown): string[] => {
  if (!isRecord(verification)) {
    return []
  }
  const { issues } = verification
  if (!Array.isArray(issues)) {
    return []
  }
  return issues.flatMap((issue) => {
    if (!isRecord(issue)) {
      return []
    }
    const code = typeof issue.code === 'string' ? issue.code : ''
    const message = typeof issue.message === 'string' ? issue.message : ''
    if (!code && !message) {
      return []
    }
    return [code ? `${code}: ${message}` : message]
  })
}

export const hasVerificationErrors = (verification: unknown): boolean => {
  if (!isRecord(verification)) {
    return false
  }
  const { errors } = verification
  return Array.isArray(errors) && errors.length > 0
}
