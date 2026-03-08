import { test, expect } from '@playwright/test'

test('homepage renders shell', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Network latency and packet loss')).toBeVisible()
  await expect(page.getByText('Collector')).toBeVisible()
})
