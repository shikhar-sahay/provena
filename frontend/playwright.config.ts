import { defineConfig } from '@playwright/test';
for (const key of ['M6_WEB_URL', 'M6_API_URL']) {
  const url = new URL(process.env[key] ?? 'https://invalid.example');
  if (process.env.M6_E2E !== '1' || url.protocol !== 'http:' || url.hostname !== '127.0.0.1') throw new Error('Use the disposable tools/run_e2e.py runner.');
}
export default defineConfig({
  testDir: './e2e', fullyParallel: false, workers: 1, retries: 0, forbidOnly: true,
  timeout: 120_000, globalTimeout: 600_000, expect: { timeout: 15_000 },
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  outputDir: `${process.env.M6_ARTIFACTS}/browser`,
  use: { baseURL: process.env.M6_WEB_URL, browserName: 'chromium', viewport: { width: 1440, height: 1000 },
    trace: 'retain-on-failure', screenshot: 'only-on-failure', actionTimeout: 15_000 },
});
