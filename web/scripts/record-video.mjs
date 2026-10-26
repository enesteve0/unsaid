// Records each scene of video/scenes.json as a silent 1920x1080 webm, against a running Unsaid server.
//   node scripts/record-video.mjs http://127.0.0.1:8080 ../video/build/rec
import { chromium } from '@playwright/test'
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

const [base = 'http://127.0.0.1:8080', out = '../video/build/rec'] = process.argv.slice(2)
const script = JSON.parse(readFileSync(new URL('../../video/scenes.json', import.meta.url)))
const [width, height] = script.size
mkdirSync(out, { recursive: true })

const only = process.env.SCENES ? process.env.SCENES.split(',') : null
const browser = await chromium.launch({ channel: 'chrome' }) // real Chrome: H.264/AAC playback
const timingPath = join(out, 'timing.json')
const timing = existsSync(timingPath) ? JSON.parse(readFileSync(timingPath)) : {}
// Cold open: the full-screen player, first as a blind student hears it, then with Unsaid.
const co = script.cold_open
for (const [id, mode, caption] of [['cold_heard', 'heard', co.first_card], ['cold_unsaid', 'unsaid', '']]) {
  if (only && !only.includes(id)) continue
  const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1, recordVideo: { dir: out, size: { width, height } } })
  const t0 = Date.now()
  const page = await context.newPage()
  const q = new URLSearchParams({ mode, voice: 'off', start: co.lecture_start, end: co.lecture_end, ...(caption ? { caption } : {}) })
  await page.goto(`${base}/cinema/${script.sample}?${q}`, { waitUntil: 'load' })
  await page.getByRole('button', { name: 'Play' }).waitFor({ timeout: 30000 })
  await page.waitForTimeout(1500)
  await page.getByRole('button', { name: 'Play' }).click()
  timing[id] = (Date.now() - t0) / 1000
  await page.waitForTimeout((co.lecture_end - co.lecture_start) * 1000 + (mode === 'unsaid' ? 6000 : 1500))
  const video = page.video()
  await context.close()
  renameSync(await video.path(), join(out, `${id}.webm`))
  console.log(`${id}: play pressed at ${timing[id].toFixed(2)} s`)
}

for (const scene of script.scenes) {
  if (only && !only.includes(scene.id)) continue
  const context = await browser.newContext({
    viewport: { width, height },
    deviceScaleFactor: 1,
    recordVideo: { dir: out, size: { width, height } },
    reducedMotion: 'no-preference',
  })
  const page = await context.newPage()
  const started = Date.now()
  for (const step of scene.actions) {
    if (step.goto) await page.goto(base + step.goto.replace('{sample}', script.sample), { waitUntil: 'load' })
    else if (step.wait) await page.waitForTimeout(step.wait)
    else if (step.hover) await page.hover(step.hover)
    else if (step.click) await page.locator(step.click).first().click()
    else if (step.scroll) await page.evaluate((y) => window.scrollTo({ top: y, behavior: 'smooth' }), step.scroll)
    else if (step.wait_for) await page.waitForSelector(step.wait_for, { timeout: step.timeout ?? 30000 })
    else if (step.wait_for_url) await page.waitForURL(step.wait_for_url, { timeout: step.timeout ?? 60000 })
  }
  const seconds = (Date.now() - started) / 1000
  const video = page.video()
  await context.close()
  const path = await video.path()
  renameSync(path, join(out, `${scene.id}.webm`))
  console.log(`${scene.id}: ${seconds.toFixed(1)} s recorded`)
}
writeFileSync(timingPath, JSON.stringify(timing, null, 1))
await browser.close()
