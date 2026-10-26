import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

// A report shaped like eval/run_eval.py's, with held-out and development clips; the numbers are fixtures.
const systems = (coverage: number) => [
  { key: 'oneshot', label: 'One-shot', metrics: { talk_over: 30, coverage: 0.5 } },
  { key: 'unsaid', label: 'Unsaid', metrics: { talk_over: 0, coverage } },
]
const REPORT = {
  available: true,
  generated_at: '2026-10-27 00:00 UTC',
  clips: 3,
  minutes: 6,
  systems: systems(0.6),
  splits: [
    { key: 'heldout', label: 'Held-out clips: labelled blind', clips: 1, minutes: 2, systems: systems(0.7) },
    { key: 'dev', label: 'Development clips: also used to develop the prompts', clips: 2, minutes: 4, systems: systems(0.5) },
  ],
  metric_labels: {
    talk_over: { label: 'Talks over lecturer', better: 'lower', unit: 's' },
    coverage: { label: 'Pointing moments covered', better: 'higher', unit: '%' },
  },
  failures: [],
  notes: ['Fixture report.'],
}

test('held-out and development results are shown separately, accessibly', async ({ page }) => {
  await page.route('**/api/eval', (route) => route.fulfill({ json: REPORT }))
  await page.goto('/evaluation')
  await expect(page.getByRole('heading', { name: 'Held-out clips: labelled blind' })).toBeVisible()
  await expect(page.getByRole('heading', { name: /Development clips/ })).toBeVisible()
  const heldout = page.getByRole('table', { name: /Held-out clips/ })
  await expect(heldout.getByRole('row', { name: /Unsaid/ })).toContainText('70%')
  await page.waitForTimeout(1200) // let entrance animations settle before measuring contrast
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
  const serious = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
  expect(serious.map((v) => `${v.id}: ${v.nodes.length} × ${v.help}`)).toEqual([])
})
