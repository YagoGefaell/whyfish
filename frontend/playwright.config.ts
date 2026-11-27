import { mkdirSync, readdirSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineConfig, devices } from '@playwright/test'

/**
 * End-to-end tests against the real backend and Stockfish (`make test-e2e`).
 * Never touches data/whyfish.db or the `make dev` ports: own temporary database and ports.
 * If a port is already in use the run fails instead of reusing whatever is there.
 */
const BACKEND_PORT = 8765
const FRONTEND_PORT = 5180
const PLATFORMS_PORT = 8766 // fake Lichess / Chess.com (e2e/fake_platforms.py)
const ARTIFACTS = resolve(import.meta.dirname, 'e2e-artifacts')

// Playwright loads this file again in every worker process. Pick the database once, in the
// main process, and hand it to the workers through the environment: deleting or renaming it
// from a worker would pull it from under the running backend.
if (!process.env.WHYFISH_E2E_DB) {
  mkdirSync(ARTIFACTS, { recursive: true })
  for (const name of readdirSync(ARTIFACTS)) {
    if (/^e2e-\d+\.db(-journal)?$/.test(name)) rmSync(resolve(ARTIFACTS, name), { force: true })
  }
  process.env.WHYFISH_E2E_DB = resolve(ARTIFACTS, `e2e-${String(Date.now())}.db`)
}
const DB = process.env.WHYFISH_E2E_DB

export default defineConfig({
  testDir: './e2e',
  // The appearance screenshots (phase 6.5) only run with `make appearance-shots`.
  testIgnore: process.env.APPEARANCE_SHOTS ? [] : ['**/appearance.spec.ts'],
  outputDir: resolve(ARTIFACTS, 'results'),
  timeout: 120_000,
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: `http://127.0.0.1:${String(FRONTEND_PORT)}`,
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'desktop-1920',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1920, height: 1080 } },
    },
    {
      name: 'desktop-1366',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1366, height: 768 } },
    },
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
  webServer: [
    {
      command: `python3 e2e/fake_platforms.py ${String(PLATFORMS_PORT)}`,
      url: `http://127.0.0.1:${String(PLATFORMS_PORT)}/health`,
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: `uv run uvicorn app.main:app --host 127.0.0.1 --port ${String(BACKEND_PORT)}`,
      cwd: resolve(import.meta.dirname, '../backend'),
      env: {
        DATABASE_URL: `sqlite:///${DB}`,
        ANALYSIS_TIME_S: '0.05',
        EVALUATE_TIME_S: '0.1',
        BOT_MOVETIME_S: '0.05',
        WHY_STEP_MS: '400',
        BOT_THINK_SCALE: '0', // no minimum "thinking" time for the bot in tests
        LICHESS_URL: `http://127.0.0.1:${String(PLATFORMS_PORT)}/lichess`,
        CHESSCOM_URL: `http://127.0.0.1:${String(PLATFORMS_PORT)}/chesscom`,
      },
      url: `http://127.0.0.1:${String(BACKEND_PORT)}/api/health`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `pnpm exec vite --host 127.0.0.1 --port ${String(FRONTEND_PORT)} --strictPort`,
      env: { BACKEND_URL: `http://127.0.0.1:${String(BACKEND_PORT)}` },
      url: `http://127.0.0.1:${String(FRONTEND_PORT)}`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
