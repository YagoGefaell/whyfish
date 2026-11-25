import { expect, test, type Browser, type Page } from '@playwright/test'

/**
 * Board rendering: pieces fill the square exactly (the cburnett SVG brings its own margin, as on
 * Lichess), and the dragged piece is the same size as at rest with the cursor at its centre.
 * Saves zoomed 4x4-square crops in e2e-artifacts/:
 *   board-{rest,drag}-dpr{1,2}.png   play board, a1-d4, at rest and mid-drag (e2 pawn over d4)
 *   board-review-dpr2.png             review board, same crop
 *   board-promotion-dpr2.png          promotion dialog over the review board
 */

interface Box {
  x: number
  y: number
  width: number
  height: number
}

async function box(page: Page, selector: string): Promise<Box> {
  const b = await page.locator(selector).first().boundingBox()
  if (!b) throw new Error(`no box for ${selector}`)
  return b
}

/** The drag overlay clone: the piece rendered outside the board grid. */
const draggedBox = (page: Page, boardId: string) =>
  box(page, `[data-piece-image]:not(#${boardId}-board *)`)

const centre = (b: Box) => ({ x: b.x + b.width / 2, y: b.y + b.height / 2 })

/** The piece on `square` takes exactly the whole square. */
async function expectPieceFillsSquare(page: Page, boardId: string, square: string) {
  const sq = await box(page, `#${boardId}-square-${square}`)
  const piece = await box(page, `#${boardId}-square-${square} [data-piece-image]`)
  for (const k of ['x', 'y', 'width', 'height'] as const) expect(piece[k]).toBeCloseTo(sq[k], 0)
}

/** Crop of files a-d, ranks 1-4 (white at the bottom). */
async function cropA1D4(page: Page, boardId: string) {
  const a4 = await box(page, `#${boardId}-square-a4`)
  return { x: a4.x, y: a4.y, width: a4.width * 4, height: a4.height * 4 }
}

async function newPage(browser: Browser, dpr: number, baseURL: string | undefined) {
  const context = await browser.newContext({
    baseURL,
    viewport: { width: 1280, height: 900 },
    deviceScaleFactor: dpr,
  })
  return { context, page: await context.newPage() }
}

// One project is enough: each test opens its own context with the pixel ratio it checks.
test.beforeEach(({ browserName }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop-1920' || browserName !== 'chromium', 'single run')
})

for (const dpr of [1, 2]) {
  test(`play board: pieces fill the square, drag keeps size (dpr ${String(dpr)})`, async ({
    browser,
    baseURL,
  }) => {
    const { context, page } = await newPage(browser, dpr, baseURL)
    await page.goto('/')
    await page.getByRole('button', { name: 'Empezar' }).click()
    await expect(page).toHaveURL(/\/play\/\d+$/)
    await expect(page.getByText(/Te toca/)).toBeVisible()

    for (const sq of ['e2', 'a1', 'g1', 'e8']) await expectPieceFillsSquare(page, 'play-board', sq)
    const clip = await cropA1D4(page, 'play-board')
    await page.screenshot({ path: `e2e-artifacts/board-rest-dpr${String(dpr)}.png`, clip })

    // Grab the e2 pawn off-centre and hold it over d4: the piece jumps to centre on the cursor.
    const e2 = await box(page, '#play-board-square-e2')
    const from = centre(e2)
    await page.mouse.move(from.x - e2.width * 0.3, from.y + e2.height * 0.3)
    await page.mouse.down()
    const d4 = centre(await box(page, '#play-board-square-d4'))
    await page.mouse.move(d4.x, d4.y, { steps: 8 })
    const dragged = await draggedBox(page, 'play-board')
    expect(dragged.width).toBeCloseTo(e2.width, 0)
    expect(dragged.height).toBeCloseTo(e2.height, 0)
    const c = centre(dragged)
    expect(Math.abs(c.x - d4.x)).toBeLessThanOrEqual(1)
    expect(Math.abs(c.y - d4.y)).toBeLessThanOrEqual(1)
    await page.screenshot({ path: `e2e-artifacts/board-drag-dpr${String(dpr)}.png`, clip })

    // Drop back on its own square: no move is made.
    await page.mouse.move(from.x, from.y, { steps: 4 })
    await page.mouse.up()
    await expectPieceFillsSquare(page, 'play-board', 'e2')
    await context.close()
  })
}

// White pawn on b7 at the end, white to move: bxa8 opens the promotion dialog.
const PROMOTION_PGN = `[Event "?"]
[Result "*"]

1. e4 d5 2. exd5 c6 3. dxc6 Nf6 4. cxb7 Nc6 *
`

test('review board and promotion dialog (dpr 2)', async ({ browser, baseURL }) => {
  const { context, page } = await newPage(browser, 2, baseURL)
  await page.goto('/import')
  await page.getByLabel('Pega el PGN').fill(PROMOTION_PGN)
  await page.getByLabel('Blancas').check()
  await page.getByRole('button', { name: 'Importar y analizar' }).click()
  await expect(page).toHaveURL(/\/review\/\d+$/)
  await page.getByRole('button', { name: 'Empezar revisión' }).click({ timeout: 90_000 })
  await page.keyboard.press('End')
  await expect(page.locator('#review-board-square-b7 [data-piece-image="wP"]')).toBeVisible()

  for (const sq of ['b7', 'e1', 'a8']) await expectPieceFillsSquare(page, 'review-board', sq)
  await page.screenshot({
    path: 'e2e-artifacts/board-review-dpr2.png',
    clip: await cropA1D4(page, 'review-board'),
  })

  const b7 = centre(await box(page, '#review-board-square-b7'))
  const a8 = centre(await box(page, '#review-board-square-a8'))
  await page.mouse.move(b7.x, b7.y)
  await page.mouse.down()
  await page.mouse.move(a8.x, a8.y, { steps: 8 })
  await page.mouse.up()
  const dialog = page.getByRole('dialog', { name: 'Elige la pieza de promoción' })
  await expect(dialog).toBeVisible()
  // Each choice shows the piece filling its button, as on a board square.
  const button = await box(page, '[role="dialog"] button[aria-label="Dama"]')
  const queen = await box(page, '[role="dialog"] button[aria-label="Dama"] [data-piece-image]')
  expect(queen.width).toBeCloseTo(queen.height, 0)
  expect(Math.abs(centre(queen).x - centre(button).x)).toBeLessThanOrEqual(0.5)
  expect(Math.abs(centre(queen).y - centre(button).y)).toBeLessThanOrEqual(0.5)
  expect(queen.width).toBeGreaterThanOrEqual(button.width - 2) // inside the 1 px border
  await page.screenshot({
    path: 'e2e-artifacts/board-promotion-dpr2.png',
    clip: await box(page, '[role="dialog"] > div'),
  })
  await context.close()
})
