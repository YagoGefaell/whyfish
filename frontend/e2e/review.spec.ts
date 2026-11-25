import { expect, test, type Page } from '@playwright/test'

const OPERA = `[Event "Paris Opera"]
[Date "1858.11.02"]
[White "Paul Morphy"]
[Black "Duke Karl / Count Isouard"]
[Result "1-0"]

1. e4 e5 2. Nf3 d6 3. d4 Bg4 4. dxe5 Bxf3 5. Qxf3 dxe5 6. Bc4 Nf6 7. Qb3 Qe7
8. Nc3 c6 9. Bg5 b5 10. Nxb5 cxb5 11. Bxb5+ Nbd7 12. O-O-O Rd8 13. Rxd7 Rxd7
14. Rd1 Qe6 15. Bxd7+ Nxd7 16. Qb8+ Nxb8 17. Rd8# 1-0
`

const shot = (page: Page, name: string, project: string) =>
  page.screenshot({ path: `e2e-artifacts/${project}-${name}.png`, fullPage: true })

test('import, analyse and review a game', async ({ page }, testInfo) => {
  const project = testInfo.project.name
  const mobile = project === 'mobile'

  await page.goto('/import')
  // As the loser (black), so the review has errors of the user to jump to.
  await page.getByLabel('Pega el PGN').fill(OPERA)
  await page.getByLabel('Negras').check()
  await page.getByRole('button', { name: 'Importar y analizar' }).click()
  await expect(page).toHaveURL(/\/review\/\d+$/)

  // While analysing, the board already shows the game. Then the summary comes first.
  const start = page.getByRole('button', { name: 'Empezar revisión' })
  await expect(start).toBeVisible({ timeout: 90_000 })
  await expect(page.getByTestId('accuracy-black')).toBeVisible()
  await shot(page, 'review-summary', project)

  // Desktop: board as big as the height allows (>= 600 px at 1366x768), everything inside the
  // window, and board + panel centred together.
  if (!mobile) {
    const viewport = page.viewportSize()
    const board = await page.getByTestId('review-board').boundingBox()
    const panel = await page.getByRole('region', { name: 'Panel de revisión' }).boundingBox()
    const bottom = await page.getByTestId('player-bottom').boundingBox()
    if (!viewport || !board || !panel || !bottom) throw new Error('layout not measured')
    if (project === 'desktop-1366') expect(board.width).toBeGreaterThanOrEqual(600)
    expect(bottom.y + bottom.height).toBeLessThanOrEqual(viewport.height)
    expect(panel.y + panel.height).toBeLessThanOrEqual(viewport.height)
    const left = board.x - 36 // vertical eval bar + gap
    const right = viewport.width - (panel.x + panel.width)
    expect(Math.abs(left - right)).toBeLessThan(48)
  }
  await expect(page.getByTestId(mobile ? 'eval-bar-horizontal' : 'eval-bar-vertical')).toBeVisible()

  await start.click()
  const panel = page.getByRole('region', { name: 'Panel de revisión' })
  await expect(panel.getByRole('heading').first()).toContainText('e4 es teoría')

  // Keyboard: next error of the user (black) with N.
  await page.keyboard.press('n')
  await expect(panel.getByRole('heading').first()).toContainText(
    / es (una imprecisión|un error|un grave error)/,
  )
  await expect(page.getByTestId('move-badge')).toBeVisible()
  await shot(page, 'review-error', project)

  // Not the best move: "La mejor era X" (+ green arrow) appears on its own; "Ver línea" unfolds it.
  await expect(panel.getByText(/La mejor era/)).toBeVisible()
  await panel.getByRole('button', { name: 'Ver línea' }).click()
  await expect(panel.getByLabel('Línea de la mejor jugada')).toBeVisible()
  await shot(page, 'review-best', project)

  // Arrow keys and the graph.
  await page.keyboard.press('ArrowRight')
  await page.getByRole('button', { name: 'Ir a 10. Nxb5' }).click()
  await expect(panel.getByRole('heading').first()).toContainText('Nxb5')

  // Explore a line from the engine details.
  await panel.getByText('Detalles del motor').click()
  await panel.getByLabel('Continuación tras la jugada').getByRole('button').first().click()
  const variant = page.getByRole('status', { name: 'Variante explorada' })
  await expect(variant).toContainText(/Evaluación [+-]?\d|Jaque mate|Tablas/, { timeout: 15_000 })
  await shot(page, 'review-variation', project)
  await page.keyboard.press('Escape')
  await expect(variant).toBeHidden()
})

test('other screens', async ({ page }, testInfo) => {
  const project = testInfo.project.name
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Nueva partida' })).toBeVisible()
  await shot(page, 'new-game', project)

  await page.getByRole('button', { name: 'Empezar' }).click()
  await expect(page).toHaveURL(/\/play\/\d+$/)
  await expect(page.getByText(/Te toca/)).toBeVisible()
  await shot(page, 'play', project)

  await page.goto('/games')
  await expect(page.getByRole('heading', { name: 'Historial' })).toBeVisible()
  await shot(page, 'history', project)

  await page.goto('/import')
  await shot(page, 'import', project)
})
