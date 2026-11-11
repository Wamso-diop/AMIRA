import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: 'tests/e2e',
  timeout: 30_000,
  reporter: [['list']],
  use: { baseURL: 'http://localhost:5310', headless: true },
  webServer: { command: 'node tests/e2e/server.mjs 5310', port: 5310, reuseExistingServer: true },
});
