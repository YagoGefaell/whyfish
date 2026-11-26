import { expect, test, type Locator, type Page } from '@playwright/test'

// 1.a3?? (Qxd4 wins the knight): Black wins the queen a few moves later.
const QUEEN = `[Event "Ver por qué"]
[SetUp "1"]
[FEN "4r1k1/5ppp/8/8/3n3Q/8/PP3P2/6K1 w - - 0 1"]
[Result "0-1"]

1. a3 Re1+ 2. Kh2 Nf3+ 3. Kh3 Nxh4 4. Kxh4 0-1
`

const shot = (page: Page, name: string, project: string) =>
  page.screenshot({ path: `e2e-artifacts/${project}-${name}.png`, fullPage: true })

const visible = (locator: Locator) => locator.locator('visible=true').first()

test('"Ver por qué" replays the sequence up to the consequence', async ({ page }, testInfo) => {
  const project = testInfo.project.name
  const mobile = project === 'mobile'

  await page.goto('/import')
  await page.getByLabel('Pega el PGN').fill(QUEEN)
  await page.getByLabel('Blancas').check()
  await page.getByRole('button', { name: 'Importar y analizar' }).click()
  await expect(page).toHaveURL(/\/review\/\d+$/)
  await page.getByRole('button', { name: 'Empezar revisión' }).click({ timeout: 90_000 })

  const panel = page.getByRole('region', { name: 'Panel de revisión' })
  await expect(panel.getByRole('heading').first()).toContainText('a3 es un grave error')
  await panel.getByRole('button', { name: 'Ver por qué' }).click()
  const replay = page.getByRole('region', { name: 'Ver por qué' })
  await expect(replay.getByRole('heading')).toContainText('Por qué 1.a3 es un error grave')

  // It plays by itself up to the consequence (the queen falls), then the final card.
  const result = visible(page.getByRole('status', { name: 'Resultado' }))
  await expect(result).toContainText(/pierdes la dama/i, { timeout: 30_000 })
  const sequence = page.getByRole('list', { name: 'Secuencia' })
  await expect(sequence.locator('[data-consequence]')).toHaveCount(1)
  await shot(page, 'why-result', project)

  // Nothing covers the board: the card is below it (mobile) or beside it (desktop).
  const board = await page.getByTestId('review-board').boundingBox()
  const card = await result.boundingBox()
  if (!board || !card) throw new Error('layout not measured')
  if (mobile) expect(card.y).toBeGreaterThanOrEqual(board.y + board.height)
  else expect(card.x).toBeGreaterThanOrEqual(board.x + board.width)

  // A step of the sequence: the replay stops there, with its caption (the check).
  await sequence.getByRole('button').nth(1).click()
  const caption = visible(page.getByLabel('Paso actual'))
  await expect(caption).toContainText('da jaque')
  await page.waitForTimeout(600) // let the pieces finish sliding back
  await shot(page, 'why-step', project)
  const text = await caption.boundingBox()
  if (!text) throw new Error('caption not measured')
  if (mobile) expect(text.y).toBeGreaterThanOrEqual(board.y + board.height)
  else expect(text.x).toBeGreaterThanOrEqual(board.x + board.width)

  // "Volver a la partida" (Esc) leaves the replay.
  await page.keyboard.press('Escape')
  await expect(replay).toBeHidden()

  // "Pruébalo tú": the best move is not shown; Esc leaves it too.
  await panel.getByRole('button', { name: 'Pruébalo tú' }).click()
  await expect(page.getByRole('region', { name: 'Pruébalo tú' })).toContainText(
    'Busca la mejor jugada para las blancas',
  )
  await shot(page, 'why-try', project)
  await page.keyboard.press('Escape')
})
