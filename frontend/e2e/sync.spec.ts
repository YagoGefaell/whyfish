import { expect, test, type Page } from '@playwright/test'

const shot = (page: Page, name: string, project: string) =>
  page.screenshot({ path: `e2e-artifacts/${project}-${name}.png`, fullPage: true })

test('sync Lichess and Chess.com accounts, filter and analyse in the background', async ({
  page,
}, testInfo) => {
  const project = testInfo.project.name

  // Ajustes: both accounts (the fake platforms serve user "e2euser").
  await page.goto('/settings')
  await page.getByLabel('Usuario de Lichess').fill('e2euser')
  await page.getByLabel('Usuario de Chess.com').fill('E2EUser') // case-insensitive
  await page.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByText('Cuentas guardadas.')).toBeVisible()
  await shot(page, 'settings', project)

  // Historial: sync (the first project imports; the others find nothing new).
  await page.goto('/games')
  await page.getByRole('button', { name: 'Sincronizar' }).click()
  const progress = page.getByRole('list', { name: 'Sincronización' })
  await expect(progress).toContainText('Lichess (e2euser): hecho', { timeout: 15_000 })
  await expect(progress).toContainText('Chess.com (E2EUser): hecho')
  await expect(page.getByText('e2euser (1500) – rival1 (1600)')).toBeVisible()
  await expect(page.getByText('e2euser (1400) – rival3 (1450)')).toBeVisible()

  // Filters (kept in the URL).
  await page.getByLabel('Origen').selectOption('chesscom')
  await expect(page).toHaveURL(/origin=chesscom/)
  await expect(page.getByText('e2euser (1400) – rival3 (1450)')).toBeVisible()
  await expect(page.getByText('e2euser (1500) – rival1 (1600)')).toBeHidden()
  await page.getByLabel('Origen').selectOption('')

  // The background queue analyses them by itself.
  await page.getByLabel('Análisis').selectOption('true')
  await expect(page.getByText('rival2 (1501) – e2euser (1601)')).toBeVisible({ timeout: 60_000 })
  await page.getByLabel('Análisis').selectOption('')
  await shot(page, 'history-synced', project)
})
