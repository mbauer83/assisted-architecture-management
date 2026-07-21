import { expect, test, type APIRequestContext, type Page } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

type Problem = { kind: string; detail: string }
type DiagramSummary = { artifact_id: string; name: string; diagram_type: string }
type DiagramList = { items: DiagramSummary[] }

const here = path.dirname(fileURLToPath(import.meta.url))
const mediaDir = path.resolve(here, '../../../../docs/media')

test.beforeEach(async ({ context }) => {
  await context.addInitScript(() => {
    localStorage.setItem('arch_group_model-project', 'uncategorized')
    localStorage.setItem('arch_group_diagram-collection', 'uncategorized')
    localStorage.setItem('arch_group_document-collection', 'uncategorized')
  })
})

function mediaPath(fileName: string): string {
  fs.mkdirSync(mediaDir, { recursive: true })
  return path.join(mediaDir, fileName)
}

function watch(page: Page): Problem[] {
  const problems: Problem[] = []
  page.on('pageerror', (err) => problems.push({ kind: 'pageerror', detail: String(err) }))
  page.on('console', (msg) => {
    if (msg.type() !== 'error') return
    if (/Failed to load resource.*status of 423/.test(msg.text()) && msg.location().url.includes('/api/assurance')) return
    problems.push({ kind: 'console.error', detail: msg.text() })
  })
  page.on('response', (resp) => {
    if (resp.url().includes('/api/') && resp.status() >= 500) {
      problems.push({ kind: `http ${resp.status()}`, detail: resp.url() })
    }
  })
  return problems
}

async function capture(page: Page, fileName: string): Promise<void> {
  await expect(page.locator('#app > main')).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(300)
  await page.screenshot({ path: mediaPath(fileName), animations: 'disabled' })
}

async function gotoAndCapture(page: Page, route: string, fileName: string): Promise<void> {
  const problems = watch(page)
  await page.goto(route, { waitUntil: 'load' })
  await capture(page, fileName)
  expect(problems, `runtime problems while capturing ${fileName}`).toEqual([])
}

async function firstDiagram(request: APIRequestContext, predicate: (diagram: DiagramSummary) => boolean): Promise<DiagramSummary> {
  const response = await request.get('/api/diagrams')
  expect(response.ok()).toBeTruthy()
  const diagrams = (await response.json() as DiagramList).items
  const match = diagrams.find(predicate)
  expect(match, 'expected seeded self-model diagram for media capture').toBeTruthy()
  return match as DiagramSummary
}

async function captureStoredDiagram(
  page: Page,
  request: APIRequestContext,
  fileName: string,
  predicate: (diagram: DiagramSummary) => boolean,
): Promise<void> {
  const diagram = await firstDiagram(request, predicate)
  const problems = watch(page)
  await page.goto(`/diagram?id=${encodeURIComponent(diagram.artifact_id)}`, { waitUntil: 'load' })
  if (diagram.diagram_type !== 'matrix') await expect(page.locator('.svg-wrap svg')).toBeVisible({ timeout: 15_000 })
  await capture(page, fileName)
  expect(problems, `runtime problems while capturing ${fileName}`).toEqual([])
}

async function captureRenderedDiagramPng(
  request: APIRequestContext,
  fileName: string,
  predicate: (diagram: DiagramSummary) => boolean,
): Promise<void> {
  const diagram = await firstDiagram(request, predicate)
  const svg = await request.get(`/api/diagram-svg?id=${encodeURIComponent(diagram.artifact_id)}`)
  expect(svg.ok()).toBeTruthy()
  const svgText = await svg.text()
  expect(svgText, `${fileName} SVG should include entity labels before PNG export`).toContain('Artifacts Promoted')

  const response = await request.get(`/api/diagram-download?id=${encodeURIComponent(diagram.artifact_id)}&format=png`)
  expect(response.ok()).toBeTruthy()
  fs.writeFileSync(mediaPath(fileName), await response.body())
}

test.describe('overview and browse media', () => {
  test('captures overview, entity list, treemap, search, and entity detail', async ({ page }) => {
    await gotoAndCapture(page, '/', 'hero-overview.png')
    await gotoAndCapture(page, '/', 'overview.png')
    await gotoAndCapture(page, '/entities?domain=application&group=platform-core', 'entities-list.png')
    await gotoAndCapture(page, '/entities?view=treemap&group=platform-core', 'treemap.png')
    await gotoAndCapture(page, '/search?q=architecture', 'search.png')

    const problems = watch(page)
    await page.goto('/entities?group=platform-core', { waitUntil: 'load' })
    const firstEntity = page.locator('main a[href*="/entity?id="]').first()
    await firstEntity.waitFor({ timeout: 10_000 })
    await firstEntity.click()
    await capture(page, 'entity-detail.png')
    expect(problems, 'runtime problems while capturing entity-detail.png').toEqual([])
  })
})

test.describe('grouping media', () => {
  test('captures group management', async ({ page }) => {
    await gotoAndCapture(page, '/entities/groups', 'group-management.png')
  })
})

test.describe('diagramming media', () => {
  test('captures stored diagram examples and create flow', async ({ page, request }) => {
    await captureRenderedDiagramPng(
      request,
      'diagram-archimate.png',
      (d) => d.artifact_id === 'ARC@1777452513.68ZZDj.promote-artifacts',
    )
    await captureStoredDiagram(page, request, 'diagram-matrix.png', (d) => d.diagram_type === 'matrix')
    await captureStoredDiagram(page, request, 'diagram-activity.png', (d) => d.diagram_type === 'activity')
    await captureStoredDiagram(page, request, 'diagram-sequence.png', (d) => d.diagram_type === 'sequence')
    await captureStoredDiagram(page, request, 'diagram-c4.png', (d) => d.diagram_type.startsWith('c4-'))
    await gotoAndCapture(page, '/diagram/create?type=c4-system-context', 'diagram-c4-create.png')
  })
})

test.describe('assurance media', () => {
  test('captures assurance overview and diagrams', async ({ page }) => {
    const problems = watch(page)
    await page.goto('/assurance', { waitUntil: 'load' })
    await expect(page.getByText('Loading assurance store status')).toHaveCount(0, { timeout: 10_000 })
    await capture(page, 'assurance-overview.png')
    expect(problems, 'runtime problems while capturing assurance-overview.png').toEqual([])
    await gotoAndCapture(page, '/assurance/diagrams?type=control-structure', 'assurance-control-structure.png')
    await gotoAndCapture(page, '/assurance/diagrams?type=bowtie', 'assurance-bowtie.png')
    await gotoAndCapture(page, '/assurance/gsn', 'assurance-gsn.png')
  })
})

// graph-explore.gif is intentionally manual: record /graph?id=<entity> after opening
// first-degree neighbours, then optimize the GIF before replacing docs/media/graph-explore.gif.

test.describe('security signals media', () => {
  /* Anchored on the repository's OWN backend component, so these images show the
     real dogfooded snapshot (its actual SBOM and CVEs) rather than a contrived
     fixture. `watch()` asserts no runtime problems, so a capture fails if the view
     is broken — the images double as a smoke test of the signals surfaces. */
  const BACKEND_ANCHOR = 'APP@1777293133.OYEmP1.architecture-backend'

  test('captures the entity panel, component vulnerabilities, and impact', async ({ page }) => {
    const problems = watch(page)
    await page.goto(`/entity?id=${encodeURIComponent(BACKEND_ANCHOR)}`, { waitUntil: 'load' })
    // The derived-attributes panel is absent until signals resolve; without this
    // wait the capture races it and silently produces a screenshot of nothing.
    await page.locator('.derived-security').waitFor({ timeout: 10_000 })
    await capture(page, 'security-entity-panel.png')
    expect(problems, 'runtime problems while capturing security-entity-panel.png').toEqual([])

    const findingProblems = watch(page)
    await page.goto(
      `/assurance/security/findings?anchor=${encodeURIComponent(BACKEND_ANCHOR)}`,
      { waitUntil: 'load' },
    )
    await page.locator('[data-testid="component-group"]').first().waitFor({ timeout: 10_000 })
    await capture(page, 'security-findings.png')
    expect(findingProblems, 'runtime problems while capturing security-findings.png').toEqual([])

    // Reached the way a user reaches it, so the capture also proves the link works.
    const impactProblems = watch(page)
    await page.locator('[data-testid="vulnerability-link"]').first().click()
    await page.locator('[data-testid="impact-headline"]').waitFor({ timeout: 10_000 })
    await capture(page, 'security-vulnerability-impact.png')
    expect(impactProblems, 'runtime problems while capturing security-vulnerability-impact.png').toEqual([])
  })
})
