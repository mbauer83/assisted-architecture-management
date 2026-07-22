import { expect, test, type Page } from '@playwright/test'
import {
  capture, captureRenderedDiagram, captureStoredDiagram, gotoAndCapture,
  resetManifest, watch, type CaptureProvenance,
} from './mediaHelpers'

const BACKEND = 'APP@1777293133.OYEmP1.architecture-backend'
const ANALYSIS = 'STPA@1784721732.pflr.3e4395'
const STRATEGY = 'ARC@1784483951.yBNaaU.strategy-overview'
const VALUE_STREAM = 'ARC@1784483996.YRywG6.value-stream-deliver-an-architecture-aligned-change'
const INVESTMENT = 'ARC@1784488894.WwyJAa.resource-investment-map'
const C4_CONTEXT = 'CSC@1780829783.z8RRON.amp-system-context'
const C4_CONTAINERS = 'CC@1780829785.Z_fI-N.amp-containers'
const C4_COMPONENTS = 'CC@1780829793.K3l46j.architecture-backend-components'

const provenance = (testName: string, artifactIds: readonly string[] = []): CaptureProvenance => ({
  test_name: testName,
  artifact_ids: artifactIds,
  synthetic_augmentation: false,
})

test.beforeAll(() => resetManifest())
test.beforeEach(async ({ context }) => {
  await context.addInitScript(() => {
    localStorage.setItem('arch_group_model-project', 'uncategorized')
    localStorage.setItem('arch_group_diagram-collection', 'uncategorized')
    localStorage.setItem('arch_group_document-collection', 'uncategorized')
  })
})

test('application entities catalog', async ({ page }) => {
  await gotoAndCapture(page, '/entities?domain=application&group=platform-core', 'entities-list.png',
    provenance('application entities catalog'))
})

test('hero application catalog', async ({ page }) => {
  await gotoAndCapture(page, '/entities?domain=application&group=platform-core', 'hero-overview.png',
    provenance('hero application catalog'))
})

test('strategy overview diagram', async ({ page, request }) => {
  await captureRenderedDiagram(page, request, 'strategy-overview.png', STRATEGY,
    'Architecture Knowledge Management', provenance('strategy overview diagram', [STRATEGY]))
})

test('architecture-aligned change value stream', async ({ page, request }) => {
  await captureRenderedDiagram(page, request, 'value-stream-deliver-change.png', VALUE_STREAM,
    'Deliver an Architecture-Aligned Change', provenance('architecture-aligned change value stream', [VALUE_STREAM]))
})

test('resource investment map', async ({ page, request }) => {
  await captureRenderedDiagram(page, request, 'resource-investment-map.png', INVESTMENT,
    'Resource Investment Map', provenance('resource investment map', [INVESTMENT]))
})

test('C4 system context', async ({ page, request }) => {
  await captureRenderedDiagram(page, request, 'c4-context.png', C4_CONTEXT,
    'AMP &#8212; System Context', provenance('C4 system context', [C4_CONTEXT]))
})

test('C4 containers', async ({ page, request }) => {
  await captureRenderedDiagram(page, request, 'c4-containers.png', C4_CONTAINERS,
    'AMP &#8212; Containers', provenance('C4 containers', [C4_CONTAINERS]))
})

test('C4 backend components', async ({ page, request }) => {
  await captureRenderedDiagram(page, request, 'c4-backend-components.png', C4_COMPONENTS,
    'Architecture Backend &#8212; Components', provenance('C4 backend components', [C4_COMPONENTS]))
})

test('re-shoot overview', async ({ page }) => {
  await gotoAndCapture(page, '/', 'overview.png', provenance('re-shoot overview'))
})

test('re-shoot search', async ({ page }) => {
  await gotoAndCapture(page, '/search?q=architecture', 'search.png', provenance('re-shoot search'))
})

test('re-shoot treemap', async ({ page }) => {
  await gotoAndCapture(page, '/entities?view=treemap&group=platform-core', 'treemap.png',
    provenance('re-shoot treemap'))
})

test('re-shoot entity detail', async ({ page }) => {
  await gotoAndCapture(page, `/entity?id=${encodeURIComponent(BACKEND)}`, 'entity-detail.png',
    provenance('re-shoot entity detail', [BACKEND]))
})

test('re-shoot group management', async ({ page }) => {
  await gotoAndCapture(page, '/entities/groups', 'group-management.png', provenance('re-shoot group management'))
})

test('re-shoot ArchiMate diagram', async ({ page, request }) => {
  const id = 'ARC@1777452513.68ZZDj.promote-artifacts'
  await captureRenderedDiagram(page, request, 'diagram-archimate.png', id,
    'Artifacts Promoted', provenance('re-shoot ArchiMate diagram', [id]))
})

test('re-shoot matrix diagram', async ({ page, request }) => {
  const id = 'MAT@1784484071.Vyfzpw.capabilities-value-stream-stages'
  await captureStoredDiagram(page, request, 'diagram-matrix.png', id,
    provenance('re-shoot matrix diagram', [id]))
})

test('re-shoot activity diagram', async ({ page, request }) => {
  const id = 'ACT@1781338474.NTuMXo.promote-engagement-work-to-the-enterprise-baseline'
  await captureStoredDiagram(page, request, 'diagram-activity.png', id,
    provenance('re-shoot activity diagram', [id]))
})

test('re-shoot sequence diagram', async ({ page, request }) => {
  const id = 'SEQ@1781338373.XPtsGv.from-a-write-to-a-consistent-broadcast-state'
  await captureStoredDiagram(page, request, 'diagram-sequence.png', id,
    provenance('re-shoot sequence diagram', [id]))
})

test('re-shoot C4 diagram', async ({ page, request }) => {
  await captureStoredDiagram(page, request, 'diagram-c4.png', C4_CONTAINERS,
    provenance('re-shoot C4 diagram', [C4_CONTAINERS]))
})

async function captureAssurance(
  page: Page, route: string, fileName: string, name: string, artifactIds: readonly string[] = [],
): Promise<void> {
  const problems = watch(page)
  await page.goto(route, { waitUntil: 'load' })
  await expect(page.getByText('Loading assurance store status')).toHaveCount(0, { timeout: 10_000 })
  await capture(page, fileName, provenance(name, artifactIds))
  expect(problems, `runtime problems while capturing ${fileName}`).toEqual([])
}

test('re-shoot assurance overview', async ({ page }) => {
  await captureAssurance(page, '/assurance', 'assurance-overview.png', 're-shoot assurance overview')
})

test('re-shoot assurance control structure', async ({ page }) => {
  await captureAssurance(page, '/assurance/diagrams?type=control-structure',
    'assurance-control-structure.png', 're-shoot assurance control structure')
})

test('re-shoot assurance bowtie', async ({ page }) => {
  await captureAssurance(page, '/assurance/diagrams?type=bowtie',
    'assurance-bowtie.png', 're-shoot assurance bowtie')
})

test('re-shoot assurance GSN', async ({ page }) => {
  await captureAssurance(page, `/assurance/gsn?analysis_id=${encodeURIComponent(ANALYSIS)}`,
    'assurance-gsn.png', 're-shoot assurance GSN', [ANALYSIS])
})

// graph-explore.gif remains a manual asset and is intentionally not regenerated.
