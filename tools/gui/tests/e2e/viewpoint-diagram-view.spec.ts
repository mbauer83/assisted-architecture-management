import { test, expect } from './coverage-fixture'

/**
 * The ad-hoc `diagram` execution representation renders through the same viewport
 * (pan/zoom, fixed-height container, resizable sidebar) and click-to-select interactivity
 * as a real persisted diagram — a large population must stay resizable/navigable rather
 * than expanding the page to its native SVG size, and entities must be selectable from a
 * sidebar exactly like `DiagramDetailView.vue`'s.
 */

test.beforeEach(async ({ context }) => {
  await context.addInitScript(() => {
    localStorage.setItem('arch_group_model-project', 'platform-core')
  })
})

test('a large viewpoint diagram renders inside a bounded, resizable viewport with a working entity sidebar', async ({ page }) => {
  await page.goto('/viewpoints/diagram?viewpoint=technology-usage')
  await expect(page.getByText(/entities:\s*\d+/i)).toBeVisible({ timeout: 15000 })

  const container = page.locator('.img-container')
  await expect(container).toBeVisible()
  const containerBox = await container.boundingBox()
  expect(containerBox).not.toBeNull()
  // The container is clamped to a sane viewport height, never the diagram's native size.
  expect(containerBox!.height).toBeLessThan(1000)

  await expect(page.locator('.sb-title', { hasText: 'Entities' })).toBeVisible()

  const firstEntity = page.locator('.ent-list .ent-item').first()
  const entityName = (await firstEntity.textContent())?.trim()
  await firstEntity.click()
  await expect(page.locator('.det-name', { hasText: entityName ?? '' })).toBeVisible()
  await expect(page.getByText('Explore in graph')).toBeVisible()
})

test('a diagram-representation viewpoint with only a small population still shows a usable, bounded viewport', async ({ page }) => {
  await page.goto('/viewpoints/diagram?viewpoint=application-structure')
  await expect(page.getByText(/entities:\s*\d+/i)).toBeVisible({ timeout: 15000 })
  await expect(page.locator('.img-container')).toBeVisible()
  await expect(page.locator('.sb-title', { hasText: 'Entities' })).toBeVisible()
})
