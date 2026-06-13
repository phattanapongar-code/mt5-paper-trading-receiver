import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      '/api': 'http://localhost:5050',
      '/ws': { target: 'ws://localhost:5050', ws: true },
      '/price': 'http://localhost:5050',
      '/health': 'http://localhost:5050',
    },
  },
})
