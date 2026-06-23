import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

const backendTarget = 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      // text for the CI log; lcov for the Codecov upload; json-summary for local glances.
      reporter: ['text-summary', 'lcov', 'json-summary'],
      include: ['src/**/*.ts', 'src/**/*.vue'],
      exclude: ['src/**/*.test.ts', 'src/domain/types.generated.ts', 'src/main.ts'],
      // Gate ONLY the logic-heavy directories where unit tests are the right tool.
      // .vue views/components and composables are wiring covered by the Playwright
      // route-walk (see e2e job), so they are measured + reported but not gated here.
      // Thresholds are seeded just below current coverage as a regression floor and
      // are meant to ratchet upward over time (cf. the backend fail_under ratchet).
      thresholds: {
        'src/domain/**': { statements: 90, lines: 90, functions: 80, branches: 80 },
        'src/ui/lib/**': { statements: 33, lines: 35, functions: 20, branches: 18 },
      },
    },
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
