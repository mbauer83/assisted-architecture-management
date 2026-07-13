import { test, expect } from './coverage-fixture'

/**
 * Viewpoint execution UX: a shipped default definition executes and renders a non-empty
 * population, and a parameterized definition prompts for typed inputs (rather than
 * failing with an opaque missing-parameter error) before its first execution.
 */

test.beforeEach(async ({ context }) => {
  await context.addInitScript(() => {
    localStorage.setItem('arch_group_model-project', 'platform-core')
    localStorage.setItem('arch_group_diagram-collection', 'uncategorized')
    localStorage.setItem('arch_group_document-collection', 'uncategorized')
  })
})

test.describe('shipped default executes non-empty', () => {
  test('a shipped exploration-representation definition renders at least one entity', async ({ page }) => {
    await page.goto('/graph?viewpoint=capability-map')
    await expect(page.getByText(/entities?:\s*\d+/i)).toBeVisible({ timeout: 15000 })
    const nodeCount = await page.locator('.graph-svg .graph-node').count()
    expect(nodeCount).toBeGreaterThan(0)
  })
})

test.describe('parameterized execution prompts typed inputs', () => {
  test('a definition with a required entity-id parameter shows a typed prompt, not a raw error', async ({ page }) => {
    await page.goto('/graph?viewpoint=element-dependents')
    await expect(page.getByRole('dialog', { name: 'Viewpoint parameters' })).toBeVisible()
    await expect(page.getByText('anchor (required)')).toBeVisible()
    // entity-id parameters use the entity picker, never a free-text id field.
    await expect(page.getByPlaceholder(/select an entity for anchor/i)).toBeVisible()
    // The Run button starts disabled until the required parameter has a value.
    await expect(page.getByRole('button', { name: 'Run' })).toBeDisabled()
  })

  test('cancelling the prompt returns to the unexecuted state without an error', async ({ page }) => {
    await page.goto('/graph?viewpoint=element-dependents')
    await expect(page.getByRole('dialog', { name: 'Viewpoint parameters' })).toBeVisible()
    await page.getByRole('button', { name: 'Cancel' }).click()
    await expect(page.getByRole('dialog', { name: 'Viewpoint parameters' })).toHaveCount(0)
  })
})

// Every typed execution error code (missing-parameter, parameter-type-mismatch,
// execution-timeout, derivation-limit, binding-cardinality-violation) has its own per-code
// display text unit-tested in viewpointExecutionErrorText.test.ts, and its REST
// {code, path, message} payload shape proven identical across all four execution routes in
// the backend's TestTypedExecutionErrors suite. The test below covers the one thing those
// unit tests can't: what actually renders on screen when a real execution call fails.

test.describe('execution failure does not show a misleading empty-result state', () => {
  test('a failed execution shows only the error banner, never the "no entities matched" diagnostics text', async ({ page }) => {
    await page.route('**/api/viewpoints/execute', (route) => route.abort('failed'))
    await page.route('**/api/viewpoints/execute-projection', (route) => route.abort('failed'))
    await page.goto('/graph?viewpoint=element-dependents')
    await expect(page.getByRole('dialog', { name: 'Viewpoint parameters' })).toBeVisible()
    await page.getByPlaceholder(/select an entity for anchor/i).fill('Architect')
    await page.locator('[data-result]').first().click()
    await page.getByRole('button', { name: 'Run' }).click()
    await expect(page.getByText('Execution failed')).toBeVisible()
    await expect(page.getByText(/No entities in the current model match/i)).toHaveCount(0)
  })
})
