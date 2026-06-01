// @ts-check
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  use: {
    baseURL: 'http://localhost:8000',
    headless: true,
  },
  reporter: 'list',
  webServer: {
    command: 'source venv/bin/activate && uvicorn server:app --port 8000',
    port: 8000,
    reuseExistingServer: true,
    timeout: 15000,
  },
});
