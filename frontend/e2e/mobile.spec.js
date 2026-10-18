import { test, expect } from '@playwright/test'

// Mobile-only checks — run inside the `mobile` project (Pixel 7 viewport).
// On desktop these are irrelevant (MobileNav is md:hidden).

test.skip(() => test.info().project.name !== 'mobile', 'mobile-only spec')

test('MobileNav is visible and Dashboard fits the viewport', async ({ page }) => {
  await page.goto('/')
  const nav = page.getByRole('navigation', { name: 'Primary' })
  await expect(nav).toBeVisible()
  // no horizontal overflow past the viewport width
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth
  )
  expect(overflow).toBeLessThanOrEqual(2)
})

test('Spaced repetition stats do not overflow on small screens', async ({ page }) => {
  await page.goto('/spaced')
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth
  )
  expect(overflow).toBeLessThanOrEqual(2)
  await expect(page.getByText(/spaced repetition/i).first()).toBeVisible()
})

test('Toasts clear the MobileNav bar', async ({ page }) => {
  await page.goto('/chat')
  const navBox = await page.getByRole('navigation', { name: 'Primary' }).boundingBox()
  expect(navBox).toBeTruthy()
  // Toast container is z-50 above the bar — it must not be overlapped when shown.
  // We only assert the CSS anchor here (bottom offset >= nav height).
  const toast = await page.evaluate(() => {
    const el = document.querySelector('div.fixed.max-w-sm')
    return el ? getComputedStyle(el).bottom : null
  })
  if (toast) {
    expect(parseFloat(toast)).toBeGreaterThanOrEqual(navBox.height)
  }
})
