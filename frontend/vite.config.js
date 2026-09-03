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
  build: {
    rollupOptions: {
      output: {
        // Keep element-plus out of the entry chunk so async views never import
        // the entry module. Cache-busting the entry with ?v= used to load two
        // Vue runtimes and black-screen /settings.
        manualChunks(id) {
          if (id.includes('node_modules/element-plus')) return 'element-plus'
        }
      }
    }
  },
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
