import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

// A run in progress, served from fixtures: no model calls, so the progress view can be checked any time.
const RUN = 'demo-run'
const EVENTS = [
  { type: 'running' },
  { type: 'stage', stage: 'listen', label: 'Listen', status: 'done', seconds: 5.1, calls: [] },
  { type: 'stage', stage: 'understand', label: 'Understand', status: 'start', detail: 'Ultra reads the whole lecture' },
  { type: 'tick', stage: 'understand', tokens: 3140 },
]

test('a long model call shows its running token count, accessibly', async ({ page }) => {
  await page.route(`**/api/runs/${RUN}/result`, (route) => route.fulfill({ status: 404, json: { detail: 'not ready' } }))
  await page.route(`**/api/runs/${RUN}`, (route) =>
    route.fulfill({ json: { id: RUN, title: 'Lecture', status: 'running', position: 0, error: '' } }),
  )
  await page.route(`**/api/runs/${RUN}/events`, (route) =>
    route.fulfill({
      headers: { 'content-type': 'text/event-stream' },
      body: EVENTS.map((e) => `data: ${JSON.stringify(e)}\n\n`).join(''),
    }),
  )
  await page.goto(`/runs/${RUN}`)
  const understand = page.getByRole('listitem').filter({ hasText: 'Understand' })
  await expect(understand).toContainText('working… 3,140 tokens')
  // The count updates every second, so it must sit outside any live region: screen readers hear the stage start only.
  await expect(understand.locator('xpath=ancestor-or-self::*[@aria-live or @role="status"]')).toHaveCount(0)
  await page.waitForTimeout(600)
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
  const serious = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
  expect(serious.map((v) => `${v.id}: ${v.nodes.length} × ${v.help}`)).toEqual([])
})
