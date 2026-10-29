import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The API runs on :8080 in development; Vite proxies API and media requests to it.
// VITE_BASE sets the path the app is served under (the static demo on GitHub Pages lives at /unsaid/).
export default defineConfig({
  base: process.env.VITE_BASE ?? '/',
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8080',
      '/media': 'http://127.0.0.1:8080',
    },
  },
})
