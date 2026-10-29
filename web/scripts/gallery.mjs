// Devpost gallery: 3:2 screenshots (1500x1000) of the key screens of a running Unsaid.
//   node scripts/gallery.mjs https://<demo> ../video/build/gallery
import { chromium } from '@playwright/test'
import { mkdirSync, readFileSync } from 'node:fs'

const [base = 'http://127.0.0.1:8080', out = '../video/build/gallery'] = process.argv.slice(2)
const sample = JSON.parse(readFileSync(new URL('../../video/scenes.json', import.meta.url))).sample
mkdirSync(out, { recursive: true })
const browser = await chromium.launch() // Playwright's own Chromium plays the H.264 sample
const page = await browser.newPage({ viewport: { width: 1500, height: 1000 }, deviceScaleFactor: 2 })
const shots = [
  ['01-home', '/', null],
  ['02-cinema', `/cinema/${sample}?mode=unsaid&voice=off&start=0&end=1`, null],
  ['03-timeline', `/samples/${sample}`, async () => window.scrollTo(0, 560)],
  ['04-checks', `/samples/${sample}`, 'Descriptions & checks'],
  ['05-cost', `/samples/${sample}`, 'Models & cost'],
  ['06-tips', `/samples/${sample}`, 'Lecturer tips'],
  ['07-evaluation', '/evaluation', null],
  ['08-describe', '/describe', null],
]
for (const [name, path, action] of shots) {
  await page.goto(base + path, { waitUntil: 'load' })
  await page.waitForTimeout(1500)
  if (typeof action === 'string') {
    await page.getByRole('tab', { name: action }).click()
    await page.evaluate(() => window.scrollTo(0, 900))
    await page.waitForTimeout(800)
  } else if (action) {
    await page.evaluate(action)
    await page.waitForTimeout(800)
  }
  await page.screenshot({ path: `${out}/${name}.png` })
  console.log(name)
}
await browser.close()
