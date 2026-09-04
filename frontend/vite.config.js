import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import fs from 'node:fs'
import path from 'node:path'

function backendTarget() {
  try {
    const envPath = path.resolve(fileURLToPath(new URL('../backend/.env', import.meta.url)))
    const text = fs.readFileSync(envPath, 'utf8')
    const m = text.match(/^HTTP_PORT=(\d+)/m)
    const port = m ? m[1] : '8099'
    return `http://127.0.0.1:${port}`
  } catch {
    return 'http://127.0.0.1:8099'
  }
}

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  // Do not put element-plus alone in manualChunks (breaks Element Plus / Vue interop:
  // "t is not a function" → black screen). Do not cache-bust entry with ?v=;
  // Nginx no-store on index.html is enough. Settings may import shared exports
  // from the entry module which is fine as a single ES module URL.
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: backendTarget(),
        changeOrigin: true
      }
    }
  }
})
