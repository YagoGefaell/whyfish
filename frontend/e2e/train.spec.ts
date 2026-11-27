import { expect, test, type Page } from '@playwright/test'

// 2...Qh4?? hangs the queen and white misses 3.Nxh4: a ✗ exercise with one clear solution.
const MISSED = `[Event "Entrenar"]
[White "Yo"]
[Black "Rival"]
[Result "1/2-1/2"]

1. e4 e5 2. Nf3 Qh4 3. d3 Qd8 1/2-1/2
`

const shot = (page: Page, name: string, project: string) =>
  page.screenshot({ path: `e2e-artifacts/${project}-${name}.png`, fullPage: true })

async function drag(page: Page, from: string, to: string) {
  const square = async (sq: string) => {
    const box = await page.locator(`#review-board-square-${sq}`).boundingBox()
    if (!box) throw new Error(`square ${sq} not found`)
    return { x: box.x + box.width / 2, y: box.y + box.height / 2 }
  }
  const a = await square(from)
  const b = await square(to)
  await page.mouse.move(a.x, a.y)
  await page.mouse.down()
  await page.mouse.move(b.x, b.y, { steps: 8 })
  await page.mouse.up()
}

test('train with an own error: context, a wrong try, then the right move', async ({
  page,
}, testInfo) => {
  const project = testInfo.project.name

  await page.goto('/import')
  await page.getByLabel('Pega el PGN').fill(MISSED)
  await page.getByLabel('Blancas').check()
  await page.getByRole('button', { name: 'Importar y analizar' }).click()
  await expect(page.getByRole('button', { name: 'Empezar revisión' })).toBeVisible({
    timeout: 90_000,
  })

  // A session filtered like "Entrenar esto" (the newest error comes first).
  const exercise = page.getByRole('region', { name: 'Ejercicio' })
  await expect(async () => {
    await page.goto('/train?error_kind=missed_gain&phase=opening')
    await expect(exercise).toContainText('El rival acaba de cometer un error', { timeout: 2000 })
  }).toPass({ timeout: 30_000 })
  await expect(page.getByTestId('exercise-context')).toContainText(
    'Partida contra Rival (PGN), jugada 3, juegas con blancas.',
  )
  await expect(page.getByTestId('to-move')).toContainText('Juegan las blancas (tú)')
  await expect(page.getByText('Entrenando: Ganancia no vista · apertura')).toBeVisible()
  await expect(page.getByText('Ver la partida')).toBeHidden() // only once solved
  await shot(page, 'train-exercise', project)

  // A wrong try: options, then try again.
  await drag(page, 'b1', 'c3')
  await expect(exercise.getByRole('status', { name: 'Resultado' })).toContainText(
    'no es la mejor jugada',
  )
  await expect(exercise.getByRole('button', { name: 'Ver la solución' })).toBeVisible()
  await exercise.getByRole('button', { name: 'Intentar otra vez' }).click()

  // The right move: Nxh4.
  await drag(page, 'f3', 'h4')
  const result = exercise.getByRole('status', { name: 'Resultado' })
  await expect(result).toContainText('¡Bien visto!', { timeout: 15_000 })
  await expect(exercise.getByRole('button', { name: 'Ver la idea' })).toBeVisible()
  await expect(exercise.getByRole('link', { name: 'Ver la partida' })).toHaveAttribute(
    'href',
    /\/review\/\d+\?ply=4$/,
  )
  await shot(page, 'train-solved', project)
})
