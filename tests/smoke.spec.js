// @ts-check
const { test, expect } = require('@playwright/test');

const BASE = 'http://localhost:8000';

test('health endpoint returns ok', async ({ request }) => {
  const res = await request.get(`${BASE}/health`);
  expect(res.ok()).toBeTruthy();
  const json = await res.json();
  expect(json.status).toBe('ok');
  expect(json.note_count).toBeGreaterThan(0);
});

test('desktop layout loads with three panels', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(BASE);
  await expect(page.locator('#sidebar')).toBeVisible();
  await expect(page.locator('#browse-panel')).toBeVisible();
  await expect(page.locator('#chat-panel')).toBeVisible();
  await expect(page.locator('#app-title')).toContainText('Second Brain');
});

test('search returns results', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(BASE);
  await page.locator('#search-input').fill('a');
  await expect(page.locator('#search-dropdown')).toBeVisible({ timeout: 2000 });
  const results = page.locator('.search-result');
  await expect(results.first()).toBeVisible();
});

test('opening a note renders content', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(BASE);
  // Wait for sidebar to populate then click first note
  await page.waitForSelector('.note-item', { timeout: 5000 });
  await page.locator('.note-item').first().click();
  await expect(page.locator('#note-container')).toBeVisible({ timeout: 3000 });
  await expect(page.locator('#note-title')).not.toBeEmpty();
});
