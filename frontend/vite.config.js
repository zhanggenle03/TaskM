import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// 后端端口来源（优先级）：
//   1. 显式环境变量 VITE_API_TARGET（start.bat 注入，可覆盖）
//   2. backend/settings.json 的 backend_port（设置页可自定义，单一事实来源）
//   3. 环境变量 VITE_BACKEND_PORT
//   4. 默认 8000
function resolveApiTarget() {
  if (process.env.VITE_API_TARGET) return process.env.VITE_API_TARGET
  const settingsPath = path.resolve(__dirname, '../backend/settings.json')
  if (fs.existsSync(settingsPath)) {
    try {
      const s = JSON.parse(fs.readFileSync(settingsPath, 'utf-8'))
      const bp = s && s.backend_port
      if (bp && Number.isInteger(bp)) return `http://localhost:${bp}`
    } catch (e) {
      // 解析失败则回退
    }
  }
  if (process.env.VITE_BACKEND_PORT) return `http://localhost:${process.env.VITE_BACKEND_PORT}`
  return 'http://localhost:8000'
}

const frontendPort = parseInt(process.env.VITE_FRONTEND_PORT || '5173', 10)
const apiTarget = resolveApiTarget()

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
