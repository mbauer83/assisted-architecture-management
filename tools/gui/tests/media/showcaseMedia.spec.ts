import { expect, test, type Route } from '@playwright/test'
import fs from 'node:fs'
import {
  capture, watch, type CaptureProvenance,
} from './mediaHelpers'
import {
  assertSecurityPostureFixture, BACKEND, installSecurityPostureFixture, SECURITY_POSTURE_ENTITY_IDS,
} from './securityPostureFixture'

const ANALYSIS = 'STPA@1784721732.pflr.3e4395'
const HAZARD = 'HAZ@1784721764.wra3.48aefe'
interface TraceObservation { role?: string; observation?: string; status_code?: string }
interface TraceRow { pattern_results: [string, TraceObservation][] }
interface CoverageResponse { trace_table?: { rows: TraceRow[] } }

const provenance = (
  testName: string,
  artifactIds: readonly string[],
  viewpointSlug?: string,
  parameters?: Readonly<Record<string, string | readonly string[]>>,
  synthetic = false,
): CaptureProvenance => ({
  test_name: testName, artifact_ids: artifactIds, viewpoint_slug: viewpointSlug,
  parameters, synthetic_augmentation: synthetic,
})

async function normalizeCoverageDiagnostics(route: Route): Promise<void> {
  const response = await route.fetch()
  const body = await response.json() as CoverageResponse
  for (const row of body.trace_table?.rows ?? []) {
    for (const [, result] of row.pattern_results) {
      if (result.role === 'diagnostic' && result.status_code === undefined) {
        result.status_code = result.observation ?? 'not_applicable'
      }
    }
  }
  await route.fulfill({ response, json: body })
}

test('motivation coverage live fallback', async ({ page }) => {
  const parameters = {
    scope: ['goal', 'outcome', 'requirement'], gaps_only: 'true', group: ['motivation-narrative'],
  }
  const problems = watch(page)
  await page.route('**/api/viewpoints/execute', normalizeCoverageDiagnostics)
  await page.goto('/entities?viewpoint=motivation-coverage&param.scope=goal&param.scope=outcome&param.scope=requirement&param.gaps_only=true&param.group=motivation-narrative',
    { waitUntil: 'load' })
  await page.getByRole('checkbox', { name: 'gaps_only' }).check()
  await page.getByRole('textbox', { name: 'group' }).fill('motivation-narrative')
  await page.getByRole('button', { name: 'Apply' }).click()
  await expect(page.locator('.vp-trace-table')).toBeVisible({ timeout: 30_000 })
  await expect(page.locator('.vp-trace-cell--negative')).not.toHaveCount(0)
  await expect(page.locator('.vp-trace-cell--positive')).not.toHaveCount(0)
  await page.locator('.vp-trace').evaluate((element) => element.scrollIntoView({ block: 'start' }))
  await page.evaluate(() => window.scrollBy(0, -80))
  await capture(page, 'motivation-coverage-gaps.png',
    provenance('motivation coverage live fallback', [], 'motivation-coverage', parameters))
  expect(problems).toEqual([])
})

test('assurance graph explore', async ({ page }) => {
  const problems = watch(page)
  await page.goto(`/assurance/graph?node_id=${encodeURIComponent(HAZARD)}`, { waitUntil: 'load' })
  await expect(page.locator('.graph-layout')).toContainText('Renderer processes an untrusted PUML body', { timeout: 15_000 })
  await capture(page, 'assurance-graph-explore.png',
    provenance('assurance graph explore', [ANALYSIS, HAZARD]))
  expect(problems).toEqual([])
})

test('security posture viewpoint', async ({ page }) => {
  await installSecurityPostureFixture(page)
  const problems = watch(page)
  await page.goto('/viewpoints/diagram?viewpoint=security-posture', { waitUntil: 'load' })
  await assertSecurityPostureFixture(page)
  await capture(page, 'security-posture-viewpoint.png',
    provenance('security posture viewpoint', SECURITY_POSTURE_ENTITY_IDS, 'security-posture', {}, true))
  expect(problems).toEqual([])
})

test('stamped security export', async ({ page }) => {
  await installSecurityPostureFixture(page)
  await page.route('**/api/viewpoints/export-render', async (route) => {
    const response = await route.fetch()
    const normalized = (await response.text())
      .replace(/TLP:[A-Z]+ — basis [^<]+/,
        `TLP:WHITE — basis ${BACKEND}: SYNTHETIC-DOCS-001 — generated 2026-07-22T00:00:00Z`)
    await route.fulfill({ response, body: normalized })
  })
  await page.goto('/viewpoints/diagram?viewpoint=security-posture', { waitUntil: 'load' })
  await assertSecurityPostureFixture(page)
  const downloadEvent = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export stamped SVG' }).click()
  const download = await downloadEvent
  const downloadPath = await download.path()
  expect(downloadPath).not.toBeNull()
  const exported = fs.readFileSync(downloadPath as string, 'utf8')
  expect(exported).toContain('TLP:WHITE')
  expect(exported).toContain('id="classification-banner"')
  expect(exported).toContain('#df3725')
  expect(exported).toContain('9.1 CVSS')
  await page.setContent(`<div id="app"><main><div class="synthetic">Synthetic documentation data</div><div class="stamp">Stamped SVG · TLP:WHITE · basis ${BACKEND}: SYNTHETIC-DOCS-001</div>${exported}</main></div><style>
    body{margin:0}.synthetic{background:#7c2d12;color:#fff;padding:8px;text-align:center;font-weight:700}
    .stamp{background:#1e293b;color:#fff;padding:7px 12px;font:600 13px sans-serif}
    main{height:900px;overflow:hidden}svg{display:block;max-width:100%;max-height:815px;margin:auto}
  </style>`)
  await capture(page, 'security-export-stamped.png',
    provenance('stamped security export', SECURITY_POSTURE_ENTITY_IDS, 'security-posture', {}, true))
})

test('guidance wizard context', async ({ page }) => {
  const problems = watch(page)
  await page.goto('/model/wizard', { waitUntil: 'load' })
  await page.getByRole('button', { name: /Application/ }).click()
  await page.getByRole('button', { name: /Start the guided application questionnaire/ }).click()
  const details = page.locator('details.type-guidance')
  await details.locator('summary').click()
  await expect(details).toContainText('domain:')
  await expect(details).toContainText('Create application components')
  await capture(page, 'guidance-wizard-context.png',
    provenance('guidance wizard context', []))
  expect(problems).toEqual([])
})

test('assurance method workflow', async ({ page }) => {
  const problems = watch(page)
  await page.goto(`/assurance/stpa?analysis_id=${encodeURIComponent(ANALYSIS)}`, { waitUntil: 'load' })
  await page.getByRole('button', { name: /Review/ }).click()
  await expect(page.locator('.review-status')).toBeVisible({ timeout: 15_000 })
  await expect(page.locator('.wiz')).toContainText('PlantUML Preprocessor Untrusted-Input Disclosure')
  await capture(page, 'assurance-method-workflow.png',
    provenance('assurance method workflow', [ANALYSIS]))
  expect(problems).toEqual([])
})
