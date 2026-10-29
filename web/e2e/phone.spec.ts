import { expect, test } from '@playwright/test'

// WCAG 1.4.10 Reflow: at 320 CSS px wide (and on a common 390 px phone) nothing may need sideways scrolling.
for (const width of [320, 390]) {
  test(`every page fits a ${width} px wide screen without sideways scrolling`, async ({ browser }) => {
    const page = await browser.newPage({ viewport: { width, height: 800 } })
    const sample = (await (await page.request.get('/api/samples')).json())[0]?.id
    for (const path of ['/', '/describe', '/evaluation', '/about', ...(sample ? [`/samples/${sample}`] : [])]) {
      await page.goto(path, { waitUntil: 'networkidle' })
      await page.waitForTimeout(600)
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
      expect(overflow, `${path} overflows by ${overflow}px`).toBeLessThanOrEqual(1)
    }
    await page.close()
  })
}
