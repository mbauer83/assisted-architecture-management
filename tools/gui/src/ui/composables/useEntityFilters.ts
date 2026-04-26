import { computed, inject, onMounted, ref } from 'vue'
import { Effect } from 'effect'
import { DOMAIN_OPTIONS } from '../lib/domains'
import { modelServiceKey } from '../keys'
import type { WriteHelp } from '../../domain'

export function useEntityFilters() {
  const svc = inject(modelServiceKey)!
  const selectedDomains = ref<string[]>([])
  const selectedEntityTypes = ref<string[]>([])
  const writeHelp = ref<WriteHelp | null>(null)
  const domainOptions = DOMAIN_OPTIONS.filter((o) => o.key)

  const availableEntityTypes = computed(() => {
    const map = writeHelp.value?.entity_types_by_domain ?? {}
    const buckets = selectedDomains.value.length
      ? selectedDomains.value.flatMap((d) => map[d] ?? [])
      : Object.values(map).flat()
    return [...new Set(buckets)].sort()
  })

  const toggle = (arr: string[], val: string) =>
    arr.includes(val) ? arr.filter((v) => v !== val) : [...arr, val]

  onMounted(() => {
    void Effect.runPromise(svc.getWriteHelp())
      .then((data) => { writeHelp.value = data })
      .catch(() => {})
  })

  return { selectedDomains, selectedEntityTypes, domainOptions, availableEntityTypes, toggle }
}
