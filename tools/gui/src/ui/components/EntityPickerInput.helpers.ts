/**
 * Pure helpers for EntityPickerInput fixed-level display and widen constraints.
 * Extracted for testability (no .vue import required).
 */
import type { EntityDisplayInfo, ReferenceSearchHit } from '../../domain'

export type WidenableTo = 'none' | 'domain' | 'group'

/** Adapt an entity-display-search result item to the picker's generic result-hit shape. */
export function entityDisplayInfoToHit(entity: EntityDisplayInfo): ReferenceSearchHit {
  return {
    artifact_id: entity.artifact_id,
    record_type: 'entity',
    name: entity.name,
    status: entity.status,
    path: '',
    artifact_type: entity.artifact_type,
    domain: entity.domain,
  }
}

/** Whether the interactive filter stage should be shown. */
export function calcHasStageUI(
  fixedDomains: string[] | undefined,
  fixedEntityTypes: string[] | undefined,
  widenableTo: WidenableTo | undefined,
): boolean {
  if (widenableTo === 'none') return false
  return !(fixedDomains?.length && fixedEntityTypes?.length)
}

/** Whether the "← Back" navigation button should be shown. */
export function calcCanGoBack(
  currentStage: 'scope' | 'entity-type',
  fixedDomains: string[] | undefined,
  widenableTo: WidenableTo | undefined,
): boolean {
  return currentStage === 'entity-type' && !fixedDomains?.length && widenableTo !== 'none'
}

/** Whether the "Entity Types →" navigation button should be shown. */
export function calcCanGoForward(
  currentStage: 'scope' | 'entity-type',
  fixedEntityTypes: string[] | undefined,
  widenableTo: WidenableTo | undefined,
): boolean {
  return currentStage === 'scope' && !fixedEntityTypes?.length && widenableTo !== 'none'
}
