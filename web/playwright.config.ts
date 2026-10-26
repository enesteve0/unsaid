import { defineConfig } from '@playwright/test'

// Runs against a live server (default: the local API on :8080 serving the built app).
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  use: { baseURL: process.env.BASE_URL ?? 'http://127.0.0.1:8080', viewport: { width: 1280, height: 800 } },
  reporter: [['list']],
})
