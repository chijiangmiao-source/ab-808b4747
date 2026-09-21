import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In dev, proxy API calls to a locally running FastAPI (default :8000).
// In production nginx performs the same proxying (see nginx.conf).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
})
