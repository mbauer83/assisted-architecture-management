import { expect, test } from '@playwright/test'

const HAZARD = 'HAZ@1784721764.wra3.48aefe'
const UCA_NAME = 'Renderer is given an untrusted PUML body carrying a file/network preprocessor directive'

test('a real assurance neighborhood supports deep-linking, expansion, selection, and zoom', async ({ page }) => {
  await page.goto(`/assurance/graph?node_id=${encodeURIComponent(HAZARD)}`)

  await expect(page.getByText('Assurance Graph', { exact: true })).toBeVisible()
  await expect(page.locator('.graph-node')).toHaveCount(4, { timeout: 15_000 })
  await expect(page.locator('.graph-edge')).toHaveCount(3)
  await expect(page.locator('.graph-sidebar')).toContainText('Renderer processes an untrusted PUML body')

  const unsafeControlAction = page.locator('.graph-node').filter({ hasText: UCA_NAME })
  await expect(unsafeControlAction).toBeVisible()
  await unsafeControlAction.dblclick()
  await expect(page.locator('.graph-node')).not.toHaveCount(4, { timeout: 15_000 })

  await unsafeControlAction.click()
  await expect(page.locator('.graph-sidebar')).toContainText(UCA_NAME)
  const detailsLink = page.locator('.graph-sidebar').getByRole('link', { name: UCA_NAME, exact: true })
  await expect(detailsLink).toHaveAttribute('href', /^\/assurance\/node\//)
  await page.getByRole('button', { name: 'Zoom in' }).click()
  await page.getByRole('button', { name: 'Fit to view' }).click()
  await detailsLink.click()
  await expect(page).toHaveURL(/\/assurance\/node\//)
})
