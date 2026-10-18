import { test, expect } from '@playwright/test'

// Smoke: pages render without crashing. No chats are sent (would invoke
// the model); backend GETs are real (backend must be running).

test('dashboard renders hero + widgets', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText(/what to learn/i).first()).toBeVisible()
  await expect(page.getByText(/today's focus/i)).toBeVisible()
})

test('chat shows welcome state', async ({ page }) => {
  await page.goto('/chat')
  await expect(page.getByText(/how can i help/i)).toBeVisible()
  await expect(page.getByPlaceholder(/ask aria/i)).toBeVisible()
})

test('admin shows memory + remote cards', async ({ page }) => {
  await page.goto('/admin')
  await expect(page.getByText(/unload ai models/i)).toBeVisible()
  await expect(page.getByText(/remote access/i)).toBeVisible()
})

test('no console errors on dashboard', async ({ page }) => {
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))
  await page.goto('/')
  await page.waitForTimeout(3000)
  expect(errors).toEqual([])
})
