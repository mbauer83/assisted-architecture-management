import { type APIRequestContext } from '@playwright/test'
import { test, expect } from './coverage-fixture'

/**
 * Viewpoint query builder: named bindings (entity + connection selections), parameters,
 * derived attributes, and the extended comparator vocabulary (not_in/like/ilike) — all
 * authored entirely through GUI controls, no formula/text escape hatch.
 */

test.beforeEach(async ({ context }) => {
  await context.addInitScript(() => {
    localStorage.setItem('arch_group_model-project', 'platform-core')
    localStorage.setItem('arch_group_diagram-collection', 'uncategorized')
    localStorage.setItem('arch_group_document-collection', 'uncategorized')
  })
})

const uniqueSlug = (label: string) => `viewpoint-query-builder-e2e-${label}-${Date.now()}`

const removeViewpoint = async (request: APIRequestContext, slug: string) => {
  await request.post('/api/viewpoints/remove', { data: { slug, dry_run: false } })
}

const findEntry = async (request: APIRequestContext, slug: string) => {
  const resp = await request.get('/api/viewpoints')
  const body = await resp.json()
  return body.viewpoints.find((v: { slug: string }) => v.slug === slug)
}

test.describe('bindings, parameters, and derived attributes authored entirely in the GUI', () => {
  test('an entity binding, a connection binding, a parameter, and a derived attribute all round-trip through save/reload', async ({ page, request }) => {
    const slug = uniqueSlug('full-declaration')
    await page.goto('/viewpoints')
    await page.getByRole('button', { name: '+ New viewpoint' }).click()
    await page.getByRole('textbox', { name: 'slug' }).fill(slug)
    await page.getByRole('textbox', { name: 'name' }).fill('Full Declaration Test')
    await page.getByRole('button', { name: 'Query' }).click()

    // Parameter.
    await page.getByRole('button', { name: '+ Add parameter' }).click();
    (await page.getByRole('textbox', { name: 'parameter name' }).all())[0].fill('anchor')

    // Entity binding.
    await page.getByRole('button', { name: '+ Add binding' }).click()
    const bindingRows = page.locator('.binding-row')
    await bindingRows.nth(0).getByPlaceholder('binding name').fill('critical-processes')
    await bindingRows.nth(0).getByRole('radio', { name: 'entity selection' }).check()

    // Connection binding.
    await page.getByRole('button', { name: '+ Add binding' }).click()
    await bindingRows.nth(1).getByPlaceholder('binding name').fill('serving-links')
    await bindingRows.nth(1).getByRole('radio', { name: 'connection selection' }).check()

    // Derived attribute.
    await page.getByRole('button', { name: '+ Add derived attribute' }).click();
    (await page.getByRole('textbox', { name: 'attribute name' }).all())[0].fill('serving-count')

    await page.getByRole('button', { name: 'Save', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Viewpoints' })).toBeVisible()

    const entry = await findEntry(request, slug)
    expect(entry.query.parameters).toEqual([{ name: 'anchor', type: 'string' }])
    expect(entry.query.bindings).toEqual([
      { name: 'critical-processes', result_type: 'entities[]', select: 'entities', criteria: { kind: 'group', conjunction: 'and', children: [] } },
      { name: 'serving-links', result_type: 'connections[]', select: 'connections', criteria: { kind: 'group', conjunction: 'and', children: [] } },
    ])
    expect(entry.query.derived).toEqual([{ name: 'serving-count' }])

    await removeViewpoint(request, slug)
  })
})

test.describe('extended comparator vocabulary', () => {
  test('not_in, like, and ilike are reachable and round-trip', async ({ page, request }) => {
    const slug = uniqueSlug('comparators')
    await page.goto('/viewpoints')
    await page.getByRole('button', { name: '+ New viewpoint' }).click()
    await page.getByRole('textbox', { name: 'slug' }).fill(slug)
    await page.getByRole('textbox', { name: 'name' }).fill('Comparators Test')
    await page.getByRole('button', { name: 'Query' }).click()

    await page.getByRole('button', { name: '+ Add condition' }).first().click()
    const row = page.locator('.group-box.root > .row').first()
    await row.locator('select.attr').selectOption('status')
    await row.locator('select.cmp').selectOption('not_in')
    await row.locator('input.val').fill('deprecated, archived')

    await page.getByRole('button', { name: '+ Add condition' }).first().click()
    const secondRow = page.locator('.group-box.root > .row').nth(1)
    await secondRow.locator('select.attr').selectOption('name')
    await secondRow.locator('select.cmp').selectOption('ilike')
    await secondRow.locator('input.val').fill('%gateway%')

    await page.getByRole('button', { name: 'Save', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Viewpoints' })).toBeVisible()

    const entry = await findEntry(request, slug)
    expect(entry.query.entity_criteria.children).toEqual([
      { kind: 'condition', attribute: 'status', comparator: 'not_in', value: ['deprecated', 'archived'] },
      { kind: 'condition', attribute: 'name', comparator: 'ilike', value: '%gateway%' },
    ])

    await removeViewpoint(request, slug)
  })
})

test.describe('path-addressed validation into the new panels', () => {
  test('a duplicate binding name highlights the offending binding row, not just a flat error string', async ({ page }) => {
    await page.goto('/viewpoints')
    await page.getByRole('button', { name: '+ New viewpoint' }).click()
    await page.getByRole('textbox', { name: 'slug' }).fill(uniqueSlug('dup-binding'))
    await page.getByRole('textbox', { name: 'name' }).fill('Duplicate Binding Test')
    await page.getByRole('button', { name: 'Query' }).click()

    await page.getByRole('button', { name: '+ Add binding' }).click()
    await page.getByRole('button', { name: '+ Add binding' }).click()
    const bindingRows = page.locator('.binding-row')
    await bindingRows.nth(0).getByPlaceholder('binding name').fill('same-name')
    await bindingRows.nth(1).getByPlaceholder('binding name').fill('same-name')

    await page.getByRole('button', { name: 'Save', exact: true }).click()
    await expect(page.getByText(/duplicate-binding-name/i)).toBeVisible()
    await expect(page.locator('.binding-row.highlighted')).toHaveCount(1)
  })
})
