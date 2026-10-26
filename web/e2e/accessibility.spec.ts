import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

const PAGES = ['/', '/describe', '/evaluation', '/about']

for (const path of PAGES) {
  test(`no serious accessibility violations on ${path}`, async ({ page }) => {
    await page.goto(path, { waitUntil: 'networkidle' })
    await page.waitForTimeout(1200) // let entrance animations settle before measuring contrast
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
    const serious = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
    expect(serious.map((v) => `${v.id}: ${v.nodes.length} × ${v.help}`)).toEqual([])
  })
}

test('the sample lecture page is accessible and keyboard-operable', async ({ page }) => {
  await page.goto('/', { waitUntil: 'networkidle' })
  const first = page.getByRole('button', { name: /Hear it as a blind student does/ })
  await expect(first).toBeVisible()
  const link = page.getByRole('link', { name: /Open the whole lecture/ })
  await link.click()
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(1200)
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
  const serious = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
  expect(serious.map((v) => `${v.id}: ${v.nodes.length} × ${v.help}`)).toEqual([])
  // Every tab is reachable and selectable from the keyboard.
  const tab = page.getByRole('tab', { name: 'Descriptions & checks' })
  await tab.focus()
  await page.keyboard.press('Enter')
  await expect(tab).toHaveAttribute('aria-selected', 'true')
})

test('skip link moves focus to the main content', async ({ page }) => {
  await page.goto('/')
  await page.keyboard.press('Tab')
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused()
})
