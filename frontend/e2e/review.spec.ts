import { expect, test } from '@playwright/test'

const OPERA = `[Event "Paris Opera"]
[Date "1858.11.02"]
[White "Paul Morphy"]
[Black "Duke Karl / Count Isouard"]
[Result "1-0"]

1. e4 e5 2. Nf3 d6 3. d4 Bg4 4. dxe5 Bxf3 5. Qxf3 dxe5 6. Bc4 Nf6 7. Qb3 Qe7
8. Nc3 c6 9. Bg5 b5 10. Nxb5 cxb5 11. Bxb5+ Nbd7 12. O-O-O Rd8 13. Rxd7 Rxd7
14. Rd1 Qe6 15. Bxd7+ Nxd7 16. Qb8+ Nxb8 17. Rd8# 1-0
`

test('import a PGN, analyse it and review it with keyboard, graph and variations', async ({
  page,
}, testInfo) => {
  const mobile = testInfo.project.name === 'mobile'

  await page.goto('/import')
  await page.getByLabel('Pega el PGN').fill(OPERA)
  await page.getByLabel('Blancas').check()
  await page.getByRole('button', { name: 'Importar y analizar' }).click()

  await expect(page).toHaveURL(/\/review\/\d+$/)
  await expect(page.getByRole('heading', { name: /Revisión: Paul Morphy/ })).toBeVisible()
  // The analysis (progress bar) finishes and the review appears.
  const next = page.getByRole('button', { name: 'Siguiente' })
  await expect(next).toBeVisible({ timeout: 90_000 })

  // Eval bar: vertical next to the board on desktop, horizontal above it on mobile.
  await expect(page.getByTestId(mobile ? 'eval-bar-horizontal' : 'eval-bar-vertical')).toBeVisible()
  await expect(page.getByTestId(mobile ? 'eval-bar-vertical' : 'eval-bar-horizontal')).toBeHidden()
  if (mobile) await expect(page.getByRole('tablist', { name: 'Secciones' })).toBeVisible()

  // Keyboard navigation.
  const detail = page.getByRole('region', { name: 'Detalle de la jugada' })
  await page.keyboard.press('ArrowRight')
  await page.keyboard.press('ArrowRight')
  await page.keyboard.press('ArrowRight')
  await expect(detail.getByRole('heading').first()).toContainText('2. Nf3')
  await expect(page.getByTestId('move-badge')).toBeVisible()

  // Click on the evaluation graph.
  await page.getByRole('button', { name: 'Ir a 9… b5' }).click()
  await expect(detail.getByRole('heading').first()).toContainText('9… b5')

  await page.screenshot({
    path: `e2e-artifacts/review-${testInfo.project.name}.png`,
    fullPage: true,
  })

  // Explore the engine's best line: evaluated by the engine, then back to the game.
  await detail.getByLabel('Línea de la mejor jugada').getByRole('button').first().click()
  const variant = page.getByRole('status', { name: 'Variante explorada' })
  await expect(variant).toBeVisible()
  await expect(variant).toContainText(/Evaluación [+-]?\d|Jaque mate|Tablas/, { timeout: 15_000 })
  await page.screenshot({
    path: `e2e-artifacts/review-${testInfo.project.name}-variation.png`,
    fullPage: true,
  })
  await page.keyboard.press('Escape')
  await expect(variant).toBeHidden()

  if (mobile) {
    await page.getByRole('tab', { name: 'Resumen' }).click()
  }
  await expect(page.getByRole('table', { name: 'Resumen' })).toBeVisible()
  await expect(page.getByText('Philidor Defense', { exact: false }).first()).toBeVisible()
})
