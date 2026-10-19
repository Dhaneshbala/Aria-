import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  expect: { timeout: 10000 },
  // Start a real backend + frontend for the suite if none is already up
  // (reuses the user's running instance instead of colliding with it).
  webServer: [
    {
      command: 'cd ../backend && ../.venv/bin/python -m uvicorn main:app --port 8000',
      url: 'http://localhost:8000/api/health',
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: 'npm run dev',
      url: 'http://localhost:5173',
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
  // Use the installed Google Chrome instead of downloading browsers.
  use: { baseURL: 'http://localhost:5173', channel: 'chrome', trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    // Phones are a first-class platform (README quick-start) — catch
    // regressions like overlapping bottom bars or cramped grids.
    {
      name: 'mobile',
      use: {
        ...devices['Pixel 7'],
        channel: 'chrome',
      },
    },
  ],
})
