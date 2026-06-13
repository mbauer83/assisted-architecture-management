import { test, expect, type Page } from '@playwright/test'

/**
 * Route-walk smoke test.
 *
 * For every GUI route we assert three runtime-wiring invariants that the unit suite
 * (which mocks dependencies) cannot see:
 *   1. no API request returns 4xx/5xx  — catches the backend 422 dependency regression
 *   2. no uncaught page error          — catches the blank-page render crash
 *   3. <main> renders non-empty text   — catches "header only" blanks
 *
 * Detail routes are reached by clicking the first item in their list view so we never
 * hard-code artifact ids and we exercise the real /api/ontology and /api/diagram-context
 * calls that the 422 bug broke.
 */

type Problem = { kind: string; detail: string }

// Seed the per-axis "active group" keys so list views behave like a returning user and
// render their lists, instead of the first-visit redirect to the group-management page.
test.beforeEach(async ({ context }) => {
  await context.addInitScript(() => {
    localStorage.setItem('arch_group_model-project', 'uncategorized')
    localStorage.setItem('arch_group_diagram-collection', 'uncategorized')
    localStorage.setItem('arch_group_document-collection', 'uncategorized')
  })
})

function watch(page: Page): { problems: Problem[] } {
  const problems: Problem[] = []
  page.on('pageerror', (err) => problems.push({ kind: 'pageerror', detail: String(err) }))
  page.on('console', (msg) => {
    if (msg.type() === 'error') problems.push({ kind: 'console.error', detail: msg.text() })
  })
  page.on('response', (resp) => {
    const url = resp.url()
    if (url.includes('/api/') && resp.status() >= 400) {
      problems.push({ kind: `http ${resp.status()}`, detail: url })
    }
  })
  return { problems }
}

async function expectHealthyMain(page: Page, problems: Problem[]): Promise<void> {
  const main = page.locator('main')
  await expect(main).toBeVisible()
  const text = (await main.innerText()).trim()
  expect(text.length, 'main content should not be empty (header-only blank)').toBeGreaterThan(0)
  expect(problems, `runtime problems:\n${problems.map((p) => `  [${p.kind}] ${p.detail}`).join('\n')}`).toEqual([])
}

const STATIC_ROUTES = [
  '/',
  '/entities',
  '/entities?domain=motivation',
  '/entities/groups',
  '/documents',
  '/diagrams',
  '/search',
  '/promote',
  '/assurance',
  '/assurance/analyses',
  '/global/entities',
  '/global/diagrams',
]

for (const route of STATIC_ROUTES) {
  test(`route renders cleanly: ${route}`, async ({ page }) => {
    const { problems } = watch(page)
    await page.goto(route, { waitUntil: 'load' })
    await page.waitForTimeout(1500)
    await expectHealthyMain(page, problems)
  })
}

test('entity detail renders (exercises /api/ontology connection editor)', async ({ page }) => {
  const { problems } = watch(page)
  await page.goto('/entities', { waitUntil: 'load' })
  const firstEntity = page.locator('main a[href*="/entity?id="]').first()
  await firstEntity.waitFor({ timeout: 10000 })
  await firstEntity.click()
  await page.waitForTimeout(2000)
  await expectHealthyMain(page, problems)
})

test('diagram detail renders (exercises /api/diagram-context)', async ({ page }) => {
  const { problems } = watch(page)
  await page.goto('/diagrams', { waitUntil: 'load' })
  const firstDiagram = page.locator('main a[href*="/diagram?id="]').first()
  await firstDiagram.waitFor({ timeout: 10000 })
  await firstDiagram.click()
  await page.waitForTimeout(2500)
  await expectHealthyMain(page, problems)
})
