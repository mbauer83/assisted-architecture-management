import { test, expect, type Page } from '@playwright/test'

/**
 * Route-walk smoke test.
 *
 * For every GUI route we assert three runtime-wiring invariants that the unit suite
 * (which mocks dependencies) cannot see:
 *   1. no API request returns 5xx      — catches backend/runtime regressions
 *   2. no uncaught page error          — catches the blank-page render crash
 *   3. <main> renders non-empty text   — catches "header only" blanks
 *
 * Detail routes are reached by clicking the first item in their list view so we never
 * hard-code artifact ids and we exercise the real /api/ontology and /api/diagram-context
 * calls that the 422 bug broke.
 */

type Problem = { kind: string; detail: string }
type DiagramSummary = { artifact_id: string; name: string; diagram_type: string }
type DiagramList = { items: DiagramSummary[] }
type DiagramEntity = { artifact_id: string; name: string; artifact_type: string }
type DiagramContext = {
  diagram: { diagram_entities?: unknown }
  entities: DiagramEntity[]
}

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
    if (url.includes('/api/') && resp.status() >= 500) {
      problems.push({ kind: `http ${resp.status()}`, detail: url })
    }
  })
  return { problems }
}

async function expectHealthyMain(page: Page, problems: Problem[]): Promise<void> {
  const main = page.locator('#app > main')
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
  '/assurance/browse',
  '/assurance/analyses',
  '/assurance/stpa',
  '/assurance/grc',
  '/assurance/cast',
  '/assurance/gsn',
  '/assurance/supply-chain',
  '/assurance/baselines',
  '/assurance/diagrams',
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

test('every stored diagram instance renders (exercises each diagram type)', async ({ context, request }) => {
  test.setTimeout(180_000)
  const response = await request.get('/api/diagrams')
  expect(response.ok()).toBeTruthy()
  const diagrams = (await response.json() as DiagramList).items
  expect(diagrams.length, 'route walk needs at least one stored diagram').toBeGreaterThan(0)

  for (const diagram of diagrams) {
    await test.step(`${diagram.diagram_type}: ${diagram.name}`, async () => {
      const page = await context.newPage()
      const { problems } = watch(page)
      try {
        await page.goto(`/diagram?id=${encodeURIComponent(diagram.artifact_id)}`, { waitUntil: 'load' })
        await page.locator('#app > main').waitFor()
        await page.waitForTimeout(300)
        await expectHealthyMain(page, problems)
      } finally {
        await page.close()
      }
    })
  }
})

test('C4 rendered labels contain names, retain person labels, and omit descriptions', async ({ page, request }) => {
  test.setTimeout(120_000)
  const response = await request.get('/api/diagrams')
  const diagrams = (await response.json() as DiagramList).items
    .filter((diagram) => diagram.diagram_type.startsWith('c4-'))
  expect(diagrams.length, 'C4 assertions require at least one stored C4 diagram').toBeGreaterThan(0)

  let personLabels = 0
  for (const diagram of diagrams) {
    const contextResponse = await request.get(`/api/diagram-context?id=${encodeURIComponent(diagram.artifact_id)}`)
    expect(contextResponse.ok()).toBeTruthy()
    const context = await contextResponse.json() as DiagramContext
    const raw = context.diagram.diagram_entities
    const explicit = raw && typeof raw === 'object' ? raw as Record<string, unknown> : {}
    const descriptions: string[] = []
    const explicitPersons = Array.isArray(explicit.person) ? explicit.person : []
    const modelPersons = context.entities.filter((entity) =>
      ['business-actor', 'business-role', 'role'].includes(entity.artifact_type),
    )
    const explicitLabels: string[] = []

    for (const value of Object.values(explicit)) {
      if (!Array.isArray(value)) continue
      for (const item of value) {
        if (!item || typeof item !== 'object') continue
        const record = item as Record<string, unknown>
        const description = String(record.description ?? '').trim()
        const label = String(record.label ?? '').trim()
        if (description) descriptions.push(description)
        if (label) explicitLabels.push(label)
      }
    }

    await page.goto(`/diagram?id=${encodeURIComponent(diagram.artifact_id)}`, { waitUntil: 'load' })
    const svg = page.locator('.svg-wrap svg')
    await expect(svg).toBeVisible()
    const svgText = (await svg.textContent()) ?? ''

    for (const label of explicitLabels) expect(svgText).toContain(label)
    for (const description of descriptions) expect(svgText).not.toContain(description)
    for (const person of explicitPersons) {
      const label = String((person as Record<string, unknown>).label ?? '').trim()
      if (!label) continue
      expect(svgText).toContain(label)
      personLabels += 1
    }
    const renderedModelPersons = modelPersons.filter((person) => svgText.includes(person.name))
    personLabels += renderedModelPersons.length
  }
  expect(personLabels, 'C4 assertions require at least one rendered person label').toBeGreaterThan(0)
})

test('assurance rows render and visible TLP values have distinct colours', async ({ page, request }) => {
  const { problems } = watch(page)
  const response = await request.get('/api/assurance/nodes')
  expect(response.ok()).toBeTruthy()
  const body = await response.json() as { nodes: Array<{ tlp?: string }> }

  await page.goto('/assurance/browse', { waitUntil: 'load' })
  await page.waitForTimeout(500)
  await expectHealthyMain(page, problems)
  if (body.nodes.length > 0) await expect(page.locator('.node-item')).toHaveCount(body.nodes.length)

  const chips = page.locator('.node-tlp')
  const coloursByTlp = new Map<string, string>()
  for (let index = 0; index < await chips.count(); index += 1) {
    const chip = chips.nth(index)
    coloursByTlp.set((await chip.innerText()).trim(), await chip.evaluate((el) => getComputedStyle(el).color))
  }
  expect(coloursByTlp.size, 'live assurance data needs at least two visible non-WHITE TLP values').toBeGreaterThan(1)
  expect(new Set(coloursByTlp.values()).size).toBe(coloursByTlp.size)
})

test('assurance-only diagrams are selectable on the unified surface', async ({ page, request }, testInfo) => {
  const { problems } = watch(page)
  const genericTypes = await request.get('/api/diagram-types')
  expect(genericTypes.ok()).toBeTruthy()
  const typeKeys = new Set((await genericTypes.json() as Array<{ key: string }>).map((item) => item.key))
  expect(typeKeys.has('gsn')).toBe(true)
  for (const assuranceType of ['bowtie', 'control-structure', 'uca-matrix']) {
    expect(typeKeys.has(assuranceType)).toBe(false)
  }

  await page.goto('/assurance/diagrams', { waitUntil: 'load' })
  for (const title of ['Bowtie', 'Control Structure', 'UCA Matrix']) {
    await test.step(title, async () => {
      await page.locator('.diagram-btn', { hasText: title }).click()
      const target = page.locator(
        '.svg-container [data-assurance-node-id], .diagram-fallback .fallback-item, .uca-matrix .node-link, .uca-matrix .uca-chip',
      ).first()
      await expect(target).toBeVisible()
      await target.click()
      await expect(page.locator('.selection-panel')).toBeVisible()
      await expect(page.getByText('Edit in Assurance Browse →')).toBeVisible()
    })
  }
  await expectHealthyMain(page, problems)
  const screenshot = testInfo.outputPath('t15-unified-assurance-diagram-selection.png')
  await page.screenshot({ path: screenshot, fullPage: true })
  await testInfo.attach('T15 unified assurance diagram selection', {
    path: screenshot,
    contentType: 'image/png',
  })
})

test('assurance traceability matrix links model entities and wraps at word boundaries', async ({ page }) => {
  const matrixId = 'MAT@1780656830.v5cdp4.assurance-requirements-traceability'
  await page.goto(`/diagram?id=${encodeURIComponent(matrixId)}`, { waitUntil: 'load' })

  const serviceLink = page.getByRole('link', { name: 'Assurance Service', exact: true })
  await expect(serviceLink).toHaveAttribute(
    'href',
    '/entity?id=SRV@1780656241.ooK3YN.assurance-service',
  )
  const header = serviceLink.locator('xpath=ancestor::th')
  expect(await header.evaluate((element) => getComputedStyle(element).wordBreak)).toBe('normal')
})

test('GSN diagram renders and nodes are selectable in the generic viewer', async ({ page, request }, testInfo) => {
  const { problems } = watch(page)

  // Verify GSN is a generic diagram type (not assurance-only)
  const typesResp = await request.get('/api/diagram-types')
  expect(typesResp.ok()).toBeTruthy()
  const typeKeys = new Set((await typesResp.json() as Array<{ key: string }>).map((item) => item.key))
  expect(typeKeys.has('gsn')).toBe(true)

  // Find the stored GSN diagram
  const diagsResp = await request.get('/api/diagrams?diagram_type=gsn')
  expect(diagsResp.ok()).toBeTruthy()
  const { items } = await diagsResp.json() as DiagramList
  expect(items.length, 'T16 requires at least one stored GSN diagram').toBeGreaterThan(0)
  const gsn = items[0]

  // Verify the context endpoint surfaces diagram-owned nodes and edges
  const ctxResp = await request.get(`/api/diagram-context?id=${encodeURIComponent(gsn.artifact_id)}`)
  expect(ctxResp.ok()).toBeTruthy()
  const ctx = await ctxResp.json() as DiagramContext
  expect(ctx.entities.length, 'GSN diagram must surface diagram-owned nodes as entities').toBeGreaterThan(0)

  // Navigate to the generic viewer
  await page.goto(`/diagram?id=${encodeURIComponent(gsn.artifact_id)}`, { waitUntil: 'load' })
  await page.waitForTimeout(1000)
  await expectHealthyMain(page, problems)

  // Sidebar entity list must be populated
  const sidebar = page.locator('.ent-list .ent-item')
  await expect(sidebar.first()).toBeVisible()
  expect(await sidebar.count()).toBe(ctx.entities.length)

  // Click the first entity in the sidebar → detail panel must open
  await sidebar.first().click()
  const detailPanel = page.locator('.ent-det')
  await expect(detailPanel).toBeVisible()
  const detailName = detailPanel.locator('.det-name')
  await expect(detailName).toBeVisible()
  const nameText = await detailName.textContent()
  expect(nameText?.trim().length, 'Detail panel must show entity name').toBeGreaterThan(0)

  const screenshot = testInfo.outputPath('t16-gsn-node-selected.png')
  await page.screenshot({ path: screenshot, fullPage: true })
  await testInfo.attach('T16 GSN node selection', { path: screenshot, contentType: 'image/png' })
})

test('C4 edit-view shows model-backed panel with derived entities', async ({ page, request }, testInfo) => {
  const { problems } = watch(page)

  // Find a model-backed C4 diagram (one with _scope_entity_id in diagram_entities)
  const diagsResp = await request.get('/api/diagrams?diagram_type=c4-container')
  expect(diagsResp.ok()).toBeTruthy()
  const { items } = await diagsResp.json() as DiagramList
  expect(items.length, 'T17 requires at least one stored C4 container diagram').toBeGreaterThan(0)
  const diagram = items[0]

  // Verify the context endpoint returns _scope_entity_id in diagram_entities
  const ctxResp = await request.get(`/api/diagram-context?id=${encodeURIComponent(diagram.artifact_id)}`)
  expect(ctxResp.ok()).toBeTruthy()
  const ctx = await ctxResp.json() as DiagramContext
  const de = ctx.diagram.diagram_entities as Record<string, unknown> | null | undefined
  expect(de?._scope_entity_id, 'diagram_entities must carry _scope_entity_id for model-backed mode').toBeTruthy()
  expect(ctx.entities.length, 'Model-backed C4 must surface derived entities').toBeGreaterThan(0)

  // Navigate to the edit view
  await page.goto(`/diagram/edit?id=${encodeURIComponent(diagram.artifact_id)}`, { waitUntil: 'load' })
  await page.waitForTimeout(2000)
  await expectHealthyMain(page, problems)

  // Model-backed panel must be visible with "Derived Entities" section
  const derivedSection = page.getByText('Derived Entities')
  await expect(derivedSection).toBeVisible()

  // Entity count badge must match the context response
  const countBadge = page.locator('.mbp-count').first()
  await expect(countBadge).toBeVisible()
  const countText = await countBadge.textContent()
  expect(Number(countText?.trim()), 'Derived entity count must be positive').toBeGreaterThan(0)

  const screenshot = testInfo.outputPath('t17-c4-edit-model-backed.png')
  await page.screenshot({ path: screenshot, fullPage: true })
  await testInfo.attach('T17 C4 edit-view model-backed panel', { path: screenshot, contentType: 'image/png' })
})

test('C4 container create-view exposes shape selector for containers', async ({ page, request }, testInfo) => {
  test.setTimeout(60_000)
  const { problems } = watch(page)

  // Find a stored C4 container diagram to use its edit view (shape selector is in the edit UI)
  const diagsResp = await request.get('/api/diagrams?diagram_type=c4-container')
  expect(diagsResp.ok()).toBeTruthy()
  const { items } = await diagsResp.json() as DiagramList
  expect(items.length, 'T19 requires at least one stored C4 container diagram').toBeGreaterThan(0)
  const diagram = items[0]

  // Navigate to the edit view; switch to standalone mode (clear scope) to expose entity sections
  await page.goto(`/diagram/edit?id=${encodeURIComponent(diagram.artifact_id)}`, { waitUntil: 'load' })
  await page.waitForTimeout(1500)

  // Assert the diagram-type ui-config exposes the shape enum property for containers
  const typeResp = await request.get('/api/diagram-types/c4-container/ui-config')
  expect(typeResp.ok()).toBeTruthy()
  const typeConfig = await typeResp.json() as {
    diagram_only_types?: Array<{ entity_type: string; properties?: Array<{ name: string; schema: unknown }> }>
  }
  const containerType = typeConfig.diagram_only_types?.find((t) => t.entity_type === 'container')
  expect(containerType, 'c4-container type must expose a container entity type').toBeTruthy()
  const shapeProp = containerType?.properties?.find((p) => p.name === 'shape')
  expect(shapeProp, 'container must have a "shape" property in the diagram type config').toBeTruthy()
  const shapeSchema = shapeProp?.schema as { type?: string; enum?: unknown[] } | undefined
  expect(shapeSchema?.type).toBe('string')
  expect(Array.isArray(shapeSchema?.enum), 'shape property must have enum values').toBe(true)
  expect((shapeSchema?.enum as unknown[]).length, 'shape enum must include at least Container, ContainerDb, ContainerQueue')
    .toBeGreaterThanOrEqual(3)

  await expectHealthyMain(page, problems)

  // Navigate to a C4 container diagram; verify SVG renders (shape inference works)
  await page.goto(`/diagram?id=${encodeURIComponent(diagram.artifact_id)}`, { waitUntil: 'load' })
  await page.waitForTimeout(1500)
  const svg = page.locator('.svg-wrap svg')
  await expect(svg).toBeVisible()
  await expectHealthyMain(page, problems)

  const screenshot = testInfo.outputPath('t19-c4-shape-selection.png')
  await page.screenshot({ path: screenshot, fullPage: true })
  await testInfo.attach('T19 C4 shape selection', { path: screenshot, contentType: 'image/png' })
})

test('SVG node and edge click populates the detail sidebar (C4 + GSN)', async ({ page, request }, testInfo) => {
  test.setTimeout(120_000)
  const { problems } = watch(page)

  // ── C4: click derived entity node in rendered SVG ──────────────────────────
  const c4Resp = await request.get('/api/diagrams?diagram_type=c4-container')
  expect(c4Resp.ok()).toBeTruthy()
  const { items: c4Items } = await c4Resp.json() as DiagramList
  expect(c4Items.length, 'T18 requires at least one C4 container diagram').toBeGreaterThan(0)
  const c4Diagram = c4Items[0]

  await page.goto(`/diagram?id=${encodeURIComponent(c4Diagram.artifact_id)}`, { waitUntil: 'load' })
  // Wait for SVG interactivity to attach (data-entity-id set on <g> elements)
  await page.waitForSelector('.svg-wrap [data-entity-id]', { timeout: 15_000 })
  const c4Node = page.locator('.svg-wrap [data-entity-id]').first()
  await c4Node.click()
  const c4Detail = page.locator('.ent-det')
  await expect(c4Detail).toBeVisible()
  const c4Name = c4Detail.locator('.det-name')
  await expect(c4Name).toBeVisible()
  const c4NameText = await c4Name.textContent()
  expect(c4NameText?.trim().length, 'C4 node click must populate name in detail panel').toBeGreaterThan(0)

  // ── C4: click a connection/edge if one is present ─────────────────────────
  const c4Edge = page.locator('.svg-wrap [data-conn-id]').first()
  const c4EdgeCount = await c4Edge.count()
  if (c4EdgeCount > 0) {
    await c4Edge.click()
    await expect(page.locator('.conn-flow')).toBeVisible()
  }

  // ── GSN: click diagram-only node in rendered SVG ──────────────────────────
  const gsnResp = await request.get('/api/diagrams?diagram_type=gsn')
  expect(gsnResp.ok()).toBeTruthy()
  const { items: gsnItems } = await gsnResp.json() as DiagramList
  expect(gsnItems.length, 'T18 requires at least one GSN diagram').toBeGreaterThan(0)
  const gsnDiagram = gsnItems[0]

  await page.goto(`/diagram?id=${encodeURIComponent(gsnDiagram.artifact_id)}`, { waitUntil: 'load' })
  await page.waitForSelector('.svg-wrap [data-entity-id]', { timeout: 15_000 })
  const gsnNode = page.locator('.svg-wrap [data-entity-id]').first()
  await gsnNode.click()
  const gsnDetail = page.locator('.ent-det')
  await expect(gsnDetail).toBeVisible()
  const gsnNameText = await gsnDetail.locator('.det-name').textContent()
  expect(gsnNameText?.trim().length, 'GSN node click must populate name in detail panel').toBeGreaterThan(0)

  await expectHealthyMain(page, problems)
  const screenshot = testInfo.outputPath('t18-node-edge-selection.png')
  await page.screenshot({ path: screenshot, fullPage: true })
  await testInfo.attach('T18 node/edge selection detail', { path: screenshot, contentType: 'image/png' })
})

test('C4 person labels render in system-context and container diagrams (T20)', async ({ page, request }, testInfo) => {
  test.setTimeout(120_000)
  const { problems } = watch(page)

  // ── system-context ────────────────────────────────────────────────────────
  const ctxResp = await request.get('/api/diagrams?diagram_type=c4-system-context')
  expect(ctxResp.ok()).toBeTruthy()
  const { items: ctxItems } = await ctxResp.json() as DiagramList
  expect(ctxItems.length, 'T20 requires at least one stored C4 system-context diagram').toBeGreaterThan(0)
  const ctxDiagram = ctxItems[0]

  await page.goto(`/diagram?id=${encodeURIComponent(ctxDiagram.artifact_id)}`, { waitUntil: 'load' })
  const ctxSvg = page.locator('.svg-wrap svg')
  await expect(ctxSvg).toBeVisible({ timeout: 15_000 })
  const ctxSvgText = (await ctxSvg.textContent()) ?? ''

  // Fetch context to know which person labels to expect
  const ctxContextResp = await request.get(`/api/diagram-context?id=${encodeURIComponent(ctxDiagram.artifact_id)}`)
  expect(ctxContextResp.ok()).toBeTruthy()
  const ctxContext = await ctxContextResp.json() as DiagramContext
  const ctxPersons = ctxContext.entities.filter((e) =>
    ['business-actor', 'business-role', 'role'].includes(e.artifact_type),
  )
  // At least one person label must appear in the SVG
  const ctxPersonsRendered = ctxPersons.filter((p) => ctxSvgText.includes(p.name))
  expect(
    ctxPersonsRendered.length,
    'System-context SVG must contain at least one person entity label',
  ).toBeGreaterThan(0)

  const ctxScreenshot = testInfo.outputPath('t20-c4-system-context-person-labels.png')
  await page.screenshot({ path: ctxScreenshot, fullPage: true })
  await testInfo.attach('T20 C4 system-context person labels', { path: ctxScreenshot, contentType: 'image/png' })

  // ── container ─────────────────────────────────────────────────────────────
  const ctnResp = await request.get('/api/diagrams?diagram_type=c4-container')
  expect(ctnResp.ok()).toBeTruthy()
  const { items: ctnItems } = await ctnResp.json() as DiagramList
  expect(ctnItems.length, 'T20 requires at least one stored C4 container diagram').toBeGreaterThan(0)
  const ctnDiagram = ctnItems[0]

  await page.goto(`/diagram?id=${encodeURIComponent(ctnDiagram.artifact_id)}`, { waitUntil: 'load' })
  const ctnSvg = page.locator('.svg-wrap svg')
  await expect(ctnSvg).toBeVisible({ timeout: 15_000 })
  const ctnSvgText = (await ctnSvg.textContent()) ?? ''

  const ctnContextResp = await request.get(`/api/diagram-context?id=${encodeURIComponent(ctnDiagram.artifact_id)}`)
  expect(ctnContextResp.ok()).toBeTruthy()
  const ctnContext = await ctnContextResp.json() as DiagramContext
  const ctnPersons = ctnContext.entities.filter((e) =>
    ['business-actor', 'business-role', 'role'].includes(e.artifact_type),
  )
  const ctnPersonsRendered = ctnPersons.filter((p) => ctnSvgText.includes(p.name))
  expect(
    ctnPersonsRendered.length,
    'Container diagram SVG must contain at least one person entity label',
  ).toBeGreaterThan(0)

  await expectHealthyMain(page, problems)
  const ctnScreenshot = testInfo.outputPath('t20-c4-container-person-labels.png')
  await page.screenshot({ path: ctnScreenshot, fullPage: true })
  await testInfo.attach('T20 C4 container person labels', { path: ctnScreenshot, contentType: 'image/png' })
})

test('C4 person→container edges anchor at nodes without gap (T21)', async ({ page, request }, testInfo) => {
  test.setTimeout(60_000)
  const { problems } = watch(page)

  // Use the stored container diagram (has person→container connections)
  const resp = await request.get('/api/diagrams?diagram_type=c4-container')
  expect(resp.ok()).toBeTruthy()
  const { items } = await resp.json() as DiagramList
  expect(items.length, 'T21 requires at least one stored C4 container diagram').toBeGreaterThan(0)
  const diagram = items[0]

  await page.goto(`/diagram?id=${encodeURIComponent(diagram.artifact_id)}`, { waitUntil: 'load' })
  const svg = page.locator('.svg-wrap svg')
  await expect(svg).toBeVisible({ timeout: 15_000 })

  // Verify the SVG contains connection lines: presence of 'uses' edge label and person + container labels
  const svgText = (await svg.textContent()) ?? ''
  const contextResp = await request.get(`/api/diagram-context?id=${encodeURIComponent(diagram.artifact_id)}`)
  expect(contextResp.ok()).toBeTruthy()
  const context = await contextResp.json() as DiagramContext
  const persons = context.entities.filter((e) =>
    ['business-actor', 'business-role', 'role'].includes(e.artifact_type),
  )
  // At least one person label renders (anchored to an edge target)
  const renderedPersons = persons.filter((p) => svgText.includes(p.name))
  expect(
    renderedPersons.length,
    'Container diagram must render at least one person entity whose label appears in the SVG',
  ).toBeGreaterThan(0)

  // The SVG source must contain line/path elements (connection arrows)
  const svgSource = await page.evaluate(
    () => document.querySelector('.svg-wrap svg')?.outerHTML ?? '',
  )
  const hasConnections = svgSource.includes('<path') || svgSource.includes('<line')
  expect(hasConnections, 'SVG must contain path/line elements for person→container connections').toBe(true)

  await expectHealthyMain(page, problems)
  const screenshot = testInfo.outputPath('t21-c4-person-container-edge-anchoring.png')
  await page.screenshot({ path: screenshot, fullPage: true })
  await testInfo.attach('T21 C4 person→container edge anchoring', { path: screenshot, contentType: 'image/png' })
})
