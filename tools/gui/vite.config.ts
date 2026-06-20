import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

const backendTarget = 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
  server: {
    proxy: {
      // SSE: long-lived event stream — must NOT inherit the 10s timeout below,
      // or the dev proxy severs it (ERR_EMPTY_RESPONSE + reconnect storm).
      // Listed before '/api' so the more specific context matches first.
      '/api/events': {
        target: backendTarget,
        changeOrigin: true,
      },
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
