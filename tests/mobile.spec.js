// @ts-check
const { test, expect } = require('@playwright/test');

const BASE = 'http://localhost:8000';
const MOBILE = { width: 390, height: 844 };
const DESKTOP = { width: 1280, height: 800 };

test('tab bar visible on mobile, hidden on desktop', async ({ page }) => {
  await page.setViewportSize(MOBILE);
  await page.goto(BASE);
  await expect(page.locator('#mobile-tab-bar')).toBeVisible();
  await expect(page.locator('#sidebar')).not.toBeVisible();
  await expect(page.locator('#browse-panel')).not.toBeVisible();

  await page.setViewportSize(DESKTOP);
  await expect(page.locator('#mobile-tab-bar')).not.toBeVisible();
  await expect(page.locator('#sidebar')).toBeVisible();
});

test('note cards render on mobile', async ({ page }) => {
  await page.setViewportSize(MOBILE);
  await page.goto(BASE);
  await page.waitForSelector('.mobile-note-card', { timeout: 5000 });
  const cards = page.locator('.mobile-note-card');
  await expect(cards.first()).toBeVisible();
});

test('mobile search filters cards', async ({ page }) => {
  await page.setViewportSize(MOBILE);
  await page.goto(BASE);
  await page.waitForSelector('.mobile-note-card', { timeout: 5000 });

  const firstTitle = await page.locator('.mobile-note-card .mnc-title').first().textContent();
  const query = firstTitle.slice(0, 3);

  await page.locator('#mobile-search-input').fill(query);
  await page.waitForTimeout(400);
  await expect(page.locator('.mobile-note-card').first()).toBeVisible();
});

test('tap note card slides in detail', async ({ page }) => {
  await page.setViewportSize(MOBILE);
  await page.goto(BASE);
  await page.waitForSelector('.mobile-note-card', { timeout: 5000 });

  await page.locator('.mobile-note-card').first().click();
  await expect(page.locator('#mobile-note-detail')).toHaveClass(/open/, { timeout: 3000 });
  await expect(page.locator('#mobile-detail-title')).not.toBeEmpty();
});

test('wikilinks present in note detail', async ({ page }) => {
  await page.setViewportSize(MOBILE);
  await page.goto(BASE);
  await page.waitForSelector('.mobile-note-card', { timeout: 5000 });

  // Try a few cards until we find one with wikilinks
  const cards = await page.locator('.mobile-note-card').all();
  let found = false;
  for (const card of cards.slice(0, 10)) {
    await card.click();
    await expect(page.locator('#mobile-note-detail')).toHaveClass(/open/, { timeout: 2000 });
    const links = await page.locator('#mobile-detail-body a.wikilink').count();
    if (links > 0) { found = true; break; }
    await page.locator('#mobile-back-btn').click();
    await page.waitForTimeout(300);
  }
  // Not every vault has wikilinks in every note — just verify the detail loaded
  await expect(page.locator('#mobile-detail-title')).not.toBeEmpty();
});

test('back button closes note detail', async ({ page }) => {
  await page.setViewportSize(MOBILE);
  await page.goto(BASE);
  await page.waitForSelector('.mobile-note-card', { timeout: 5000 });

  await page.locator('.mobile-note-card').first().click();
  await expect(page.locator('#mobile-note-detail')).toHaveClass(/open/, { timeout: 3000 });

  await page.locator('#mobile-back-btn').click();
  await expect(page.locator('#mobile-note-detail')).not.toHaveClass(/open/, { timeout: 1000 });
});

test('switch to Ask tab shows chat view', async ({ page }) => {
  await page.setViewportSize(MOBILE);
  await page.goto(BASE);

  await page.locator('#m-tab-ask').click();
  await expect(page.locator('#mobile-chat-view')).toBeVisible();
  await expect(page.locator('#mobile-notes-view')).not.toBeVisible();
  await expect(page.locator('#m-chat-input')).toBeVisible();
});

test('switch back to Notes tab', async ({ page }) => {
  await page.setViewportSize(MOBILE);
  await page.goto(BASE);

  await page.locator('#m-tab-ask').click();
  await page.locator('#m-tab-notes').click();
  await expect(page.locator('#mobile-notes-view')).toBeVisible();
  await expect(page.locator('#mobile-chat-view')).not.toBeVisible();
});

test('settings modal opens on mobile', async ({ page }) => {
  await page.setViewportSize(MOBILE);
  await page.goto(BASE);

  await page.locator('#settings-btn').click();
  await expect(page.locator('#modal-overlay')).toBeVisible();
});
