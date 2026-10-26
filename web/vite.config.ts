import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The API runs on :8080 in development; Vite proxies API and media requests to it.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8080',
      '/media': 'http://127.0.0.1:8080',
    },
  },
})
