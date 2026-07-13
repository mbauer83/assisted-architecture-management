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

// Execution error-state coverage: a URL/dropdown viewpoint selection that doesn't match
// any known definition never reaches the execution call at all — the selector silently
// falls back to "None (unrestricted)" instead (confirmed by direct browser inspection;
// tracked separately as a UX question, not fixed here since it's outside this change's
// scope) — so it cannot be used to reach ViewpointExecutionError. Every typed execution
// error code (missing-parameter, parameter-type-mismatch, execution-timeout,
// derivation-limit, binding-cardinality-violation) has its own per-code display text
// unit-tested in viewpointExecutionErrorText.test.ts, and its REST {code, path, message}
// payload shape proven identical across all four execution routes in the backend's
// TestTypedExecutionErrors suite. A live-browser trigger for an actually-rendered typed
// error needs either a freshly-created definition (blocked until the newly-created-
// definition-is-immediately-executable fix lands in a running backend) or a genuinely
// slow real derivation, so end-to-end coverage of the rendered typed-error path is
// deferred, not silently dropped.
