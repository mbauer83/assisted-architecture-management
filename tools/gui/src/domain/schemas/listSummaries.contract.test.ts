import { describe, it, expect } from 'vitest'
import { Schema } from 'effect'
import { EntitySummarySchema } from './entities'
import { DocumentSummarySchema } from './documents'
import { DiagramSummarySchema } from './diagram-types'
import { tierFromIsGlobal } from '../../ui/components/TierBadge.helpers'

/**
 * List-summary contracts: `is_global` is REQUIRED on entity, document, and
 * diagram list rows (the backend always emits it), and both badge variants
 * derive from it.
 */

const ENTITY_ROW = {
  artifact_id: 'REQ@1000000901.CtrRow.contract-row',
  artifact_type: 'requirement',
  name: 'Contract Row',
  version: '0.1.0',
  status: 'draft',
  domain: 'motivation',
  subdomain: 'requirement',
  path: '/repo/model/motivation/requirement/row.md',
}

const DOCUMENT_ROW = {
  artifact_id: 'ADR@1000000902.CtrDoc.contract-document',
  doc_type: 'adr',
  title: 'Contract Document',
  status: 'draft',
  path: '/repo/docs/adr/contract-document.md',
  keywords: [],
  sections: [],
  group: 'decisions',
}

const DIAGRAM_ROW = {
  artifact_id: 'ARC@1000000903.CtrDia.contract-diagram',
  name: 'Contract Diagram',
  diagram_type: 'archimate-motivation',
  version: '0.1.0',
  status: 'draft',
  path: '/repo/diagram-catalog/diagrams/contract-diagram.puml',
  group: 'views',
}

describe('entity list summary contract', () => {
  it('accepts both badge variants', () => {
    for (const isGlobal of [true, false]) {
      const decoded = Schema.decodeUnknownSync(EntitySummarySchema)({ ...ENTITY_ROW, is_global: isGlobal })
      expect(decoded.is_global).toBe(isGlobal)
      expect(tierFromIsGlobal(decoded.is_global)).toBe(isGlobal ? 'enterprise' : 'engagement')
    }
  })

  it('rejects a row without is_global — the contract is closed', () => {
    expect(() => Schema.decodeUnknownSync(EntitySummarySchema)(ENTITY_ROW)).toThrow()
  })
})

describe('document list summary contract', () => {
  it('accepts both badge variants', () => {
    for (const isGlobal of [true, false]) {
      const decoded = Schema.decodeUnknownSync(DocumentSummarySchema)({ ...DOCUMENT_ROW, is_global: isGlobal })
      expect(decoded.is_global).toBe(isGlobal)
      expect(tierFromIsGlobal(decoded.is_global)).toBe(isGlobal ? 'enterprise' : 'engagement')
    }
  })

  it('rejects a row without is_global — the contract is closed', () => {
    expect(() => Schema.decodeUnknownSync(DocumentSummarySchema)(DOCUMENT_ROW)).toThrow()
  })
})

describe('diagram list summary contract', () => {
  it('accepts both badge variants', () => {
    for (const isGlobal of [true, false]) {
      const decoded = Schema.decodeUnknownSync(DiagramSummarySchema)({ ...DIAGRAM_ROW, is_global: isGlobal })
      expect(decoded.is_global).toBe(isGlobal)
      expect(tierFromIsGlobal(decoded.is_global)).toBe(isGlobal ? 'enterprise' : 'engagement')
    }
  })

  it('rejects a row without is_global — the contract is closed', () => {
    expect(() => Schema.decodeUnknownSync(DiagramSummarySchema)(DIAGRAM_ROW)).toThrow()
  })
})
