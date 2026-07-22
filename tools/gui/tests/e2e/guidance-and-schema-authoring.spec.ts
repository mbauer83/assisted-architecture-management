import { expect, test } from '@playwright/test'

test('the guided questionnaire presents composed domain context once above type guidance', async ({ page }) => {
  await page.goto('/model/wizard')
  await page.getByRole('button', { name: /Application/ }).click()
  await page.getByRole('button', { name: /Start the guided application questionnaire/ }).click()

  const guidance = page.locator('details.type-guidance')
  await guidance.locator('summary').click()
  const context = guidance.locator('.type-guidance__context')
  await expect(context).toHaveCount(1)
  await expect(context).toContainText('domain:')
  await expect(context).not.toHaveText(/domain:\s*$/)
  await expect(guidance.locator('.type-guidance__never')).toBeVisible()
})

test('the service specialization renders its seven effective attributes with typed controls', async ({ page }) => {
  await page.goto('/entity/create')
  const type = page.locator('select.form-select').filter({ has: page.locator('option[value="application-component"]') })
  await type.selectOption('application-component')

  const specializations = page.locator('select.form-select[multiple]')
  await expect(specializations).toBeVisible({ timeout: 15_000 })
  await specializations.selectOption('service')

  const properties = page.locator('.prop-row')
  await expect(properties).toHaveCount(7, { timeout: 15_000 })
  await expect(page.locator('.prop-key-label')).toHaveText([
    'Programming Languages & Versions', 'Frameworks & Versions', 'Runtime Environments',
    'Communication Protocols & Versions', 'Owner', 'Source Repository', 'Lifecycle State',
  ])
  await expect(page.locator('.array-input')).toHaveCount(4)
  await expect(properties.filter({ hasText: 'Lifecycle State' }).locator('select.prop-value')).toHaveValue('')
  await expect(properties.filter({ hasText: 'Lifecycle State' }).locator('option')).toHaveText([
    '—', 'Planned', 'In Development', 'Active', 'Deprecated', 'Retired',
  ])
  await expect(properties.filter({ hasText: 'Source Repository' }).locator('input[type="text"]')).toBeVisible()
})
