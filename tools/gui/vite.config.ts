import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const backendTarget = 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
        timeout: 10000,
        proxyTimeout: 10000,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req) => {
            console.log(`[vite-proxy] ${req.method} ${req.url} -> ${backendTarget}${proxyReq.path ?? '/'}`)
          })
          proxy.on('error', (err, req) => {
            console.error(`[vite-proxy] ${req.method} ${req.url} failed:`, err.message)
          })
        },
      },
      '/admin/api': {
        target: backendTarget,
        changeOrigin: true,
        timeout: 10000,
        proxyTimeout: 10000,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req) => {
            console.log(`[vite-proxy] ${req.method} ${req.url} -> ${backendTarget}${proxyReq.path ?? '/'}`)
          })
          proxy.on('error', (err, req) => {
            console.error(`[vite-proxy] ${req.method} ${req.url} failed:`, err.message)
          })
        },
      },
    },
  },
})
