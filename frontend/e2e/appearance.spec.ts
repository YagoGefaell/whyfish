import { mkdirSync, readFileSync, rmSync } from 'node:fs'
import { expect, test, type Page } from '@playwright/test'

/**
 * Appearance (phase 6.5): screens for review, in light and dark, desktop and mobile, plus the
 * boards and the piece sets. Not part of `make test-e2e`; run with `make appearance-shots`.
 * Writes to e2e-artifacts/appearance/:
 *   <mode>-<viewport>-<screen>.png   review with an error, summary, Ajustes (preview)
 *   boards.png                       every board (cburnett): preview, review, play
 *   pieces.png                       the four piece sets on the default board
 * The settings are changed through the API (the e2e database, never data/whyfish.db).
 */

const OUT = 'e2e-artifacts/appearance'
const MODES = ['light', 'dark'] as const
const BOARDS = ['brown', 'blue', 'gray', 'wood', 'slate']
const BOARD_LABEL: Record<string, string> = {
  brown: 'Marrón clásico',
  blue: 'Azul',
  gray: 'Gris',
  wood: 'Madera clara',
  slate: 'Pizarra',
}
const PIECE_SETS = ['cburnett', 'mpchess', 'chessnut', 'rhosgfx']

const OPERA = `[Event "Paris Opera"]
[White "Paul Morphy"]
[Black "Duke Karl / Count Isouard"]
[Result "1-0"]

1. e4 e5 2. Nf3 d6 3. d4 Bg4 4. dxe5 Bxf3 5. Qxf3 dxe5 6. Bc4 Nf6 7. Qb3 Qe7
8. Nc3 c6 9. Bg5 b5 10. Nxb5 cxb5 11. Bxb5+ Nbd7 12. O-O-O Rd8 13. Rxd7 Rxd7
14. Rd1 Qe6 15. Bxd7+ Nxd7 16. Qb8+ Nxb8 17. Rd8# 1-0
`

test.describe.configure({ mode: 'serial' })

test.beforeEach(({ browserName }, testInfo) => {
  const name = testInfo.project.name
  test.skip(name === 'desktop-1920' || browserName !== 'chromium', 'desktop-1366 and mobile')
})

let reviewId = 0
let playId = 0

async function setUi(page: Page, ui: { color_mode: string; board: string; pieces: string }) {
  const response = await page.request.put('/api/settings/ui', { data: ui })
  expect(response.ok()).toBe(true)
}

/** Opens a page and waits until the stored settings are applied. */
async function open(page: Page, path: string, mode: string, board: string) {
  await page.goto(path)
  await expect(page.locator(`html[data-mode="${mode}"][data-board="${board}"]`)).toHaveCount(1)
}

async function drag(page: Page, board: string, from: string, to: string) {
  const centre = async (sq: string) => {
    const box = await page.locator(`#${board}-square-${sq}`).boundingBox()
    if (!box) throw new Error(`square ${sq} not found`)
    return { x: box.x + box.width / 2, y: box.y + box.height / 2 }
  }
  const a = await centre(from)
  const b = await centre(to)
  await page.mouse.move(a.x, a.y)
  await page.mouse.down()
  await page.mouse.move(b.x, b.y, { steps: 8 })
  await page.mouse.up()
}

/** The selected move is inside the visible part of the move list. */
async function expectCurrentMoveVisible(page: Page) {
  const list = page.getByTestId('move-list')
  const current = list.locator('[aria-current="true"]')
  await expect(current).toHaveCount(1)
  await page.waitForTimeout(150)
  const [box, item] = await Promise.all([list.boundingBox(), current.boundingBox()])
  if (!box || !item) throw new Error('move list not rendered')
  expect(item.y).toBeGreaterThanOrEqual(box.y - 1)
  expect(item.y + item.height).toBeLessThanOrEqual(box.y + box.height + 1)
}

/** Settles transitions and fonts before a screenshot. */
async function settle(page: Page) {
  await page.evaluate('document.fonts.ready.then(() => true)')
  await page.waitForTimeout(450)
}

test('data: an analysed game and a game in progress', async ({ page }) => {
  test.setTimeout(240_000)
  if (reviewId !== 0) return // once per run (the database is shared by both viewports)
  await setUi(page, { color_mode: 'dark', board: 'brown', pieces: 'cburnett' })
  await page.goto('/import')
  await page.getByLabel('Pega el PGN').fill(OPERA)
  await page.getByLabel('Negras').check()
  await page.getByRole('button', { name: 'Importar y analizar' }).click()
  await expect(page.getByRole('button', { name: 'Empezar revisión' })).toBeVisible({
    timeout: 90_000,
  })
  reviewId = Number(/\/review\/(\d+)/.exec(page.url())?.[1])

  await page.goto('/')
  await page.getByRole('button', { name: 'Empezar' }).click()
  await expect(page).toHaveURL(/\/play\/\d+/)
  playId = Number(/\/play\/(\d+)/.exec(page.url())?.[1])
  for (const [from, to] of [
    ['e2', 'e4'],
    ['g1', 'f3'],
  ]) {
    await expect(page.getByText(/Te toca/)).toBeVisible({ timeout: 30_000 })
    await drag(page, 'play-board', from, to)
    await expect(page.locator(`#play-board-square-${to} [data-piece-image]`)).toBeVisible()
  }
  await expect(page.getByText(/Te toca/)).toBeVisible({ timeout: 30_000 })
})

for (const mode of MODES) {
  test(`screens: ${mode}`, async ({ page }, testInfo) => {
    const vp = testInfo.project.name === 'mobile' ? 'mobile' : 'desktop'
    mkdirSync(OUT, { recursive: true })
    const shot = async (screen: string) => {
      await settle(page)
      await page.screenshot({ path: `${OUT}/${mode}-${vp}-${screen}.png`, fullPage: true })
    }
    await setUi(page, { color_mode: mode, board: 'brown', pieces: 'cburnett' })

    // Review summary, then the first error of the user (black) with its badge.
    await open(page, `/review/${String(reviewId)}`, mode, 'brown')
    const start = page.getByRole('button', { name: 'Empezar revisión' })
    await expect(start).toBeVisible({ timeout: 60_000 })
    await expect(page.getByTestId('accuracy-black')).toBeVisible()
    await shot('2-summary')
    await start.click()
    await page.keyboard.press('n')
    await page.keyboard.press('n')
    await expect(page.getByTestId('move-badge')).toBeVisible()
    await expectCurrentMoveVisible(page)
    await shot('1-review-error')
    if (vp === 'desktop') {
      // At least 8 rows of moves at 1366×768.
      interface Box {
        clientHeight: number
        querySelector: (selector: string) => { offsetHeight: number } | null
      }
      const rows = await page
        .getByTestId('move-list')
        .evaluate((el: Box) => el.clientHeight / (el.querySelector('li')?.offsetHeight ?? 1))
      expect(rows, 'visible move rows').toBeGreaterThanOrEqual(8)
    }
    // Jumping to the end (and with the next error) keeps the move in view.
    await page.keyboard.press('End')
    await expectCurrentMoveVisible(page)
    await page.keyboard.press('Home')
    await page.getByRole('button', { name: 'Siguiente error' }).click()
    await page.getByRole('button', { name: 'Siguiente error' }).click()
    await expectCurrentMoveVisible(page)

    // Ajustes with the appearance preview.
    await open(page, '/settings', mode, 'brown')
    await expect(page.getByTestId('preview-board')).toBeVisible()
    await shot('3-settings')
  })
}

/** Joins crops into one sheet: rows of captioned images. */
async function sheet(page: Page, path: string, rows: { label: string; crops: string[] }[]) {
  const cols = Math.max(...rows.map((r) => r.crops.length))
  await page.setViewportSize({ width: 40 + cols * 346, height: 400 })
  await page.setContent(
    `<body style="margin:0;padding:16px;background:#f5f6f8;color:#1a1c20;font:600 15px sans-serif">${rows
      .map(
        (r) =>
          `<div style="margin-bottom:6px">${r.label}</div><div style="display:flex;gap:16px;margin-bottom:18px">${r.crops
            .map((c) => `<img style="width:330px" src="data:image/png;base64,${c}">`)
            .join('')}</div>`,
      )
      .join('')}</body>`,
  )
  await page.screenshot({ path, fullPage: true })
}

async function crop(page: Page, testId: string): Promise<string> {
  await settle(page)
  const path = `${OUT}/.crop.png`
  await page.getByTestId(testId).screenshot({ path })
  const data = readFileSync(path).toString('base64')
  rmSync(path)
  return data
}

test('boards and pieces', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === 'mobile', 'desktop only')
  test.setTimeout(240_000)
  mkdirSync(OUT, { recursive: true })

  // Every board with cburnett: the Ajustes preview (badge, check, arrows), the review error
  // (neutral origin, class target, marks, arrows) and the game in progress (last move).
  const rows: { label: string; crops: string[] }[] = []
  for (const board of BOARDS) {
    await setUi(page, { color_mode: 'light', board, pieces: 'cburnett' })
    const crops: string[] = []
    await open(page, '/settings', 'light', board)
    crops.push(await crop(page, 'preview-board'))
    await open(page, `/review/${String(reviewId)}`, 'light', board)
    await page.getByRole('button', { name: 'Empezar revisión' }).click()
    await page.keyboard.press('n')
    await page.keyboard.press('n')
    await expect(page.getByTestId('move-badge')).toBeVisible()
    crops.push(await crop(page, 'review-board'))
    await open(page, `/play/${String(playId)}`, 'light', board)
    await expect(page.locator('#play-board-square-e4 [data-piece-image]')).toBeVisible()
    crops.push(await crop(page, 'play-board'))
    rows.push({ label: BOARD_LABEL[board] ?? board, crops })
  }

  // The four piece sets on the default board: preview and a middlegame.
  const pieces: { label: string; crops: string[] }[] = []
  for (const set of PIECE_SETS) {
    await setUi(page, { color_mode: 'light', board: 'brown', pieces: set })
    const crops: string[] = []
    await open(page, '/settings', 'light', 'brown')
    crops.push(await crop(page, 'preview-board'))
    await open(page, `/review/${String(reviewId)}`, 'light', 'brown')
    await page.getByRole('button', { name: 'Empezar revisión' }).click()
    for (let i = 0; i < 22; i++) await page.keyboard.press('ArrowRight')
    crops.push(await crop(page, 'review-board'))
    pieces.push({ label: set === 'cburnett' ? 'cburnett (por defecto)' : set, crops })
  }
  await setUi(page, { color_mode: 'system', board: 'brown', pieces: 'cburnett' })

  await sheet(page, `${OUT}/boards.png`, rows)
  await sheet(page, `${OUT}/pieces.png`, pieces)
})
