/**
 * The management view's editable draft — mirrors `ViewpointDefinition` in
 * `src/domain/viewpoints.py`. `scope` is the simple entity/connection-type allow-list
 * shape the authoring surface supports (`viewpoint_serialization._scope_to_mapping`) —
 * `ConceptScope`'s hierarchy/endpoint predicates are not part of the authored shape and
 * so are not editable here.
 */

import { type ExecutableQueryNode, mkQuery } from './viewpointCriteria'
import { type PresentationNode } from './viewpointPresentation'

export type Purpose = 'designing' | 'deciding' | 'informing'
export type Content = 'details' | 'coherence' | 'overview'

export const VALID_PURPOSES: readonly Purpose[] = ['designing', 'deciding', 'informing']
export const VALID_CONTENTS: readonly Content[] = ['details', 'coherence', 'overview']

export interface ScopeDraft {
  entityTypes: string[] | null
  connectionTypes: string[] | null
}

export const mkScope = (): ScopeDraft => ({ entityTypes: null, connectionTypes: null })

export interface ViewpointDefinitionDraft {
  slug: string
  version: number
  name: string
  description: string
  rationale: string
  purpose: Purpose[]
  content: Content[]
  stakeholders: string[]
  concerns: string[]
  scope: ScopeDraft
  representationTypes: string[]
  derivationDefaults: Record<string, unknown>
  query: ExecutableQueryNode | null
  presentation: PresentationNode | null
}

export const mkDefinitionDraft = (): ViewpointDefinitionDraft => ({
  slug: '', version: 1, name: '', description: '', rationale: '',
  purpose: ['informing'], content: ['overview'], stakeholders: [], concerns: [],
  scope: mkScope(), representationTypes: [], derivationDefaults: {},
  query: mkQuery(), presentation: null,
})
