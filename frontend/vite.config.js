import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // Keep the charting library in its own cacheable chunk.
        manualChunks: { recharts: ['recharts'] },
      },
    },
  },
  server: {
    proxy: {
      // FastAPI runs on 127.0.0.1:8000 (python -m pft serve)
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
