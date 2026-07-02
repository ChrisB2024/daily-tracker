import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/summary': 'http://localhost:8001',
      '/reps': 'http://localhost:8001',
      '/goals': 'http://localhost:8001',
      '/rep-types': 'http://localhost:8001',
      '/debrief': 'http://localhost:8001',
      '/history': 'http://localhost:8001',
    },
  },
})
