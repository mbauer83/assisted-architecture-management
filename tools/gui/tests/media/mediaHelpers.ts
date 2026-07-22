import { expect, type APIRequestContext, type Page } from '@playwright/test'
import { createHash } from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export type Problem = { kind: string; detail: string }
export type DiagramSummary = { artifact_id: string; name: string; diagram_type: string }
type DiagramList = { items: DiagramSummary[] }

export interface CaptureProvenance {
  test_name: string
  artifact_ids: readonly string[]
  viewpoint_slug?: string
  parameters?: Readonly<Record<string, string | readonly string[]>>
  synthetic_augmentation: boolean
}

interface ManifestEntry extends Omit<CaptureProvenance, 'viewpoint_slug' | 'parameters'> {
  viewpoint_slug: string | null
  parameters: Readonly<Record<string, string | readonly string[]>>
  viewport: { width: 1440; height: 900; device_scale_factor: 2 }
  capture_tool_version: string
  output_path: string
  sha256: string
}

const here = path.dirname(fileURLToPath(import.meta.url))
const mediaDir = path.resolve(here, '../../../../docs/media')
const manifestPath = path.join(mediaDir, 'manifest.json')
const playwrightMetadata = JSON.parse(fs.readFileSync(
  path.resolve(here, '../../node_modules/@playwright/test/package.json'), 'utf8',
)) as { version: string }

export function mediaPath(fileName: string): string {
  fs.mkdirSync(mediaDir, { recursive: true })
  return path.join(mediaDir, fileName)
}

export function resetManifest(): void {
  fs.writeFileSync(manifestPath, '[]\n')
}

function record(fileName: string, provenance: CaptureProvenance): void {
  const bytes = fs.readFileSync(mediaPath(fileName))
  const current = fs.existsSync(manifestPath)
    ? JSON.parse(fs.readFileSync(manifestPath, 'utf8')) as ManifestEntry[]
    : []
  const entry: ManifestEntry = {
    ...provenance,
    viewpoint_slug: provenance.viewpoint_slug ?? null,
    parameters: provenance.parameters ?? {},
    viewport: { width: 1440, height: 900, device_scale_factor: 2 },
    capture_tool_version: `Playwright ${playwrightMetadata.version}`,
    output_path: `docs/media/${fileName}`,
    sha256: createHash('sha256').update(bytes).digest('hex'),
  }
  const merged = [...current.filter((item) => item.output_path !== entry.output_path), entry]
    .sort((left, right) => left.output_path.localeCompare(right.output_path))
  fs.writeFileSync(manifestPath, `${JSON.stringify(merged, null, 2)}\n`)
}

export function watch(page: Page): Problem[] {
  const problems: Problem[] = []
  page.on('pageerror', (err) => problems.push({ kind: 'pageerror', detail: String(err) }))
  page.on('console', (msg) => {
    if (msg.type() !== 'error') return
    if (/Failed to load resource.*status of 423/.test(msg.text()) && msg.location().url.includes('/api/assurance')) return
    problems.push({ kind: 'console.error', detail: msg.text() })
  })
  page.on('response', (response) => {
    if (response.url().includes('/api/') && response.status() >= 500) {
      problems.push({ kind: `http ${response.status()}`, detail: response.url() })
    }
  })
  return problems
}

export async function capture(
  page: Page,
  fileName: string,
  provenance: CaptureProvenance,
): Promise<void> {
  await expect(page.locator('#app > main')).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(300)
  await page.screenshot({ path: mediaPath(fileName), animations: 'disabled' })
  record(fileName, provenance)
}

export async function gotoAndCapture(
  page: Page,
  route: string,
  fileName: string,
  provenance: CaptureProvenance,
): Promise<void> {
  const problems = watch(page)
  await page.goto(route, { waitUntil: 'load' })
  await capture(page, fileName, provenance)
  expect(problems, `runtime problems while capturing ${fileName}`).toEqual([])
}

export async function diagramById(
  request: APIRequestContext,
  artifactId: string,
): Promise<DiagramSummary> {
  const response = await request.get('/api/diagrams')
  expect(response.ok()).toBeTruthy()
  const match = (await response.json() as DiagramList).items
    .find((diagram) => diagram.artifact_id === artifactId)
  expect(match, `expected diagram ${artifactId}`).toBeTruthy()
  return match as DiagramSummary
}

export async function captureStoredDiagram(
  page: Page,
  request: APIRequestContext,
  fileName: string,
  artifactId: string,
  provenance: CaptureProvenance,
): Promise<void> {
  const diagram = await diagramById(request, artifactId)
  const problems = watch(page)
  await page.goto(`/diagram?id=${encodeURIComponent(diagram.artifact_id)}`, { waitUntil: 'load' })
  if (diagram.diagram_type !== 'matrix') await expect(page.locator('.svg-wrap svg')).toBeVisible({ timeout: 15_000 })
  await capture(page, fileName, provenance)
  expect(problems, `runtime problems while capturing ${fileName}`).toEqual([])
}

export async function captureRenderedDiagram(
  page: Page,
  request: APIRequestContext,
  fileName: string,
  artifactId: string,
  expectedLabel: string,
  provenance: CaptureProvenance,
): Promise<void> {
  await diagramById(request, artifactId)
  const svg = await request.get(`/api/diagram-svg?id=${encodeURIComponent(artifactId)}`)
  expect(svg.ok()).toBeTruthy()
  expect(await svg.text(), `${fileName} should contain a stable label`).toContain(expectedLabel)
  const png = await request.get(`/api/diagram-download?id=${encodeURIComponent(artifactId)}&format=png`)
  expect(png.ok()).toBeTruthy()
  const dataUrl = `data:image/png;base64,${(await png.body()).toString('base64')}`
  await page.setContent(`<main id="render"><img alt="" src="${dataUrl}"></main><style>
    html,body,#render{width:100%;height:100%;margin:0}#render{display:flex;align-items:center;justify-content:center}
    img{display:block;max-width:100%;max-height:100%;object-fit:contain}
  </style>`)
  await page.screenshot({ path: mediaPath(fileName), animations: 'disabled' })
  record(fileName, provenance)
}

export async function addSyntheticBanner(page: Page): Promise<void> {
  await page.addInitScript(() => document.addEventListener('DOMContentLoaded', () => {
    const marker = document.createElement('div')
    marker.dataset.testid = 'synthetic-documentation-banner'
    marker.textContent = 'Synthetic documentation data'
    marker.style.cssText = 'background:#7c2d12;color:#fff;padding:8px 16px;font-weight:700;text-align:center;position:sticky;top:0;z-index:10000'
    document.body.prepend(marker)
  }))
}
