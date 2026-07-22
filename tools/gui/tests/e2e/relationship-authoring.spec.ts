import { expect, test } from '@playwright/test'

const BACKEND = 'APP@1777293133.OYEmP1.architecture-backend'

test('an existing relationship opens in the integrated editor', async ({ page }) => {
  await page.goto(`/entity?id=${encodeURIComponent(BACKEND)}`)

  const relationship = page.locator('.conn-item-wrap').filter({
    has: page.getByRole('link', { name: 'REST Interface', exact: true }),
  })
  await expect(relationship).toBeVisible()
  await relationship.locator('button[title="Edit relationship"]').click()

  await expect(relationship.getByText('Relationship properties', { exact: true })).toBeVisible()
  await expect(relationship.getByLabel('Description')).toHaveValue(
    /^Architecture Backend exposes the REST Interface/,
  )
  await relationship.getByText('Relationship properties', { exact: true }).click()
  await expect(relationship.getByText('No schema-defined properties for this relationship type.')).toBeVisible()
})

test('relationship target search offers candidates as soon as it receives focus', async ({ page }) => {
  await page.goto(`/entity?id=${encodeURIComponent(BACKEND)}`)

  const outgoing = page.locator('.conn-panel').filter({
    has: page.getByRole('heading', { name: 'Outgoing connections', exact: true }),
  })
  const targetGroup = outgoing.locator('.type-group').filter({
    has: page.getByText('application-interface', { exact: true }),
  })
  await targetGroup.locator('button[title="Add connection"]').click()
  const search = targetGroup.getByPlaceholder('Search target entity...')
  await search.focus()

  await expect(targetGroup.locator('.ep-drop')).toBeVisible()
  await expect(targetGroup.locator('.ep-drop').getByText('REST Interface', { exact: true })).toBeVisible()
})
