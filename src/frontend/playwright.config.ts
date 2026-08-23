import { defineConfig, devices } from '@playwright/test'

/**
 * Points at the compose-published front-end. No `webServer` block: the stack is brought
 * up by the pytest `compose_stack` fixture, so Playwright must not start a second copy
 * of anything.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: process.env.FRONTEND_BASE_URL ?? 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
