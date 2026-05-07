import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// VITE_BASE_PATH controls the base URL:
//   - AWS (served at /dashboard/): set VITE_BASE_PATH=/dashboard/
//   - Vercel (served at /):        leave unset or set VITE_BASE_PATH=/
export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE_PATH || '/dashboard/',
  server: {
    proxy: {
      '/api': {
        target: 'http://65.0.204.4:18080',
        changeOrigin: true
      },
      '/health': {
        target: 'http://65.0.204.4:18080',
        changeOrigin: true
      }
    }
  }
})
