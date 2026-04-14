import { ref, type Ref } from 'vue'
import { Effect, Exit, Cause } from 'effect'

export interface AsyncState<A> {
  readonly data: Ref<A | null>
  readonly error: Ref<string | null>
  readonly loading: Ref<boolean>
}

export interface AsyncHandle<A> extends AsyncState<A> {
  /** Execute an Effect, writing success/failure into the reactive state. */
  run<E>(effect: Effect.Effect<A, E, never>): void
}

/**
 * Bridges Effect execution into Vue reactive state.
 * This is the framework boundary: Effects become loading/data/error refs.
 * Errors are serialised to strings here — the only place we lose type info.
 */
export const useAsync = <A>(): AsyncHandle<A> => {
  const data: Ref<A | null> = ref(null)
  const error: Ref<string | null> = ref(null)
  const loading: Ref<boolean> = ref(false)

  function run<E>(effect: Effect.Effect<A, E, never>): void {
    loading.value = true
    error.value = null
    Effect.runPromiseExit(effect).then((exit) => {
      loading.value = false
      if (Exit.isSuccess(exit)) {
        data.value = exit.value
      } else {
        error.value = Cause.pretty(exit.cause)
      }
    })
  }

  return { data, error, loading, run }
}
