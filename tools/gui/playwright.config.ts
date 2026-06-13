import { defineConfig, devices } from '@playwright/test'

/**
 * E2E smoke configuration.
 *
 * Targets a already-running stack via E2E_BASE_URL (default: the Vite dev server on
 * :5173, which proxies /api to the backend on :8000). In CI the SPA is built and served
 * by arch-backend on :8000, so E2E_BASE_URL=http://localhost:8000.
 *
 * These tests assert runtime wiring the unit suite cannot: that every route renders
 * without a 4xx/5xx API call, an uncaught console error, or an empty <main>.
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [['github'], ['list']] : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    trace: 'on-first-retry',
    viewport: { width: 1440, height: 900 },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
