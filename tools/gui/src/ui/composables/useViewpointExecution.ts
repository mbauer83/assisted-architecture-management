import { ref } from 'vue'
import { Effect } from 'effect'
import type { ModelService } from '../../application/ModelService'
import type { ViewpointExecutionResult, ViewpointProjection } from '../../domain'
import { readErrorMessage } from '../lib/errors'

/**
 * Fetches a viewpoint's fixed §7.1 content and its styled repository projection together
 * (companion plan §6.1/§7) — the one data source every execution representation (WU-E8
 * exploration; WU-E9 table/matrix/diagram) builds on, so they can never disagree about
 * what a viewpoint returned.
 */
export function useViewpointExecution(svc: ModelService) {
  const result = ref<ViewpointExecutionResult | null>(null)
  const projection = ref<ViewpointProjection | null>(null)
  const loading = ref(false)
  const errorMessage = ref<string | null>(null)
  let lastParams: { slug?: string; query?: unknown } | null = null

  const execute = async (params: { slug?: string; query?: unknown }): Promise<void> => {
    lastParams = params
    loading.value = true
    errorMessage.value = null
    try {
      const [contentResult, projectionResult] = await Promise.all([
        Effect.runPromise(svc.executeViewpoint(params)),
        Effect.runPromise(svc.executeViewpointProjection(params)),
      ])
      result.value = contentResult
      projection.value = projectionResult
    } catch (reason) {
      errorMessage.value = readErrorMessage(reason)
      result.value = null
      projection.value = null
    } finally {
      loading.value = false
    }
  }

  const rerun = (): Promise<void> => (lastParams ? execute(lastParams) : Promise.resolve())

  const clear = (): void => {
    result.value = null
    projection.value = null
    errorMessage.value = null
    lastParams = null
  }

  return { result, projection, loading, errorMessage, execute, rerun, clear }
}
