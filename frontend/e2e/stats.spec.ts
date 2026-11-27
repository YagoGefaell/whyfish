import { expect, test, type Page } from '@playwright/test'

// A real game (PGN) with an error that is always an error: 2.g4?? allows mate in one.
const FOOLS_MATE = `[Event "Fool's mate"]
[White "Yo"]
[Black "Rival"]
[Result "0-1"]

1. f3 e5 2. g4 Qh4# 0-1
`

const shot = (page: Page, name: string, project: string) =>
  page.screenshot({ path: `e2e-artifacts/${project}-${name}.png`, fullPage: true })

test('statistics of real games link to the positions that explain them', async ({
  page,
}, testInfo) => {
  const project = testInfo.project.name

  await page.goto('/import')
  await page.getByLabel('Pega el PGN').fill(FOOLS_MATE)
  await page.getByLabel('Blancas').check()
  await page.getByRole('button', { name: 'Importar y analizar' }).click()
  await expect(page.getByRole('button', { name: 'Empezar revisión' })).toBeVisible({
    timeout: 90_000,
  })

  // The statistics are calculated in the background right after the analysis.
  await page.goto('/stats')
  const status = page.getByRole('status', { name: 'Partidas analizadas' })
  await expect(async () => {
    await page.reload()
    await expect(status).toContainText(/Basado en [1-9]\d* partidas? analizadas?/, {
      timeout: 1000,
    })
  }).toPass({ timeout: 30_000 })
  await expect(status).toContainText('solo partidas reales')
  await expect(page.getByRole('heading', { name: 'Errores por fase' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Aperturas' })).toBeVisible()
  await shot(page, 'stats', project)

  // A figure -> its positions -> the review at that move ("Mate permitido": 2.g4??).
  const kinds = page.locator('section', { hasText: 'Tipos de error más frecuentes' })
  await expect(kinds).toContainText('Mate permitido')
  const mate = kinds.locator('li', { hasText: 'Mate permitido' })
  await mate.getByText('Ver posiciones').click()
  await mate.getByRole('link').first().click()
  await expect(page).toHaveURL(/\/review\/\d+\?ply=\d+$/)
  await expect(page.getByRole('tab', { name: 'Revisión' })).toHaveAttribute('aria-selected', 'true')
  await expect(
    page.getByRole('region', { name: 'Panel de revisión' }).getByRole('heading').first(),
  ).toContainText(/es (una imprecisión|un error|un grave error|una oportunidad perdida)/)
})
