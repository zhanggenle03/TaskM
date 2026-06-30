import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const frontendPort = parseInt(process.env.VITE_FRONTEND_PORT || '5173', 10)
const apiTarget = process.env.VITE_API_TARGET || `http://localhost:${process.env.VITE_BACKEND_PORT || '8000'}`

export default defineConfig({
  plugins: [vue()],
  server: {
    port: frontendPort,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/uploads': {
        target: apiTarget,
        changeOrigin: true,
      }
    }
  }
})
