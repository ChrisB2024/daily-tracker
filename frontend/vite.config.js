import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/summary': 'http://localhost:8000',
      '/reps': 'http://localhost:8000',
      '/goals': 'http://localhost:8000',
      '/rep-types': 'http://localhost:8000',
      '/debrief': 'http://localhost:8000',
      '/history': 'http://localhost:8000',
    },
  },
})
