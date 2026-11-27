import { describe, expect, it } from 'vitest'
import css from './tokens.css?raw'
import { BOARDS } from './prefs'

/**
 * Tokens (phase 6.5): WCAG contrast of the text and badge symbols in both modes, and, for every
 * board, that coordinates, highlights, marks and arrows stand out from the squares. Visibility
 * on the board is a colour difference in OKLab (ΔE, 0-1; ~0.02 is barely noticeable) of the
 * highlight composited over the square, as the browser draws it.
 */

type Rgba = [number, number, number, number]

function parse(value: string): Rgba | null {
  const hex = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(value)
  if (hex?.[1]) {
    const h = hex[1].length === 3 ? hex[1].replace(/./g, '$&$&') : hex[1]
    return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)).concat(1) as Rgba
  }
  const rgb = /^rgb\((\d+) (\d+) (\d+)(?: \/ ([\d.]+))?\)$/.exec(value)
  if (rgb) return [Number(rgb[1]), Number(rgb[2]), Number(rgb[3]), Number(rgb.at(4) ?? 1)]
  return null
}

function block(selector: string): Record<string, Rgba> {
  const start = css.indexOf(selector)
  if (start < 0) return {}
  const body = css.slice(start, css.indexOf('\n}', start))
  const out: Record<string, Rgba> = {}
  for (const m of body.matchAll(/--color-([\w-]+):\s*([^;]+);/g)) {
    const color = parse(m[2].trim())
    if (color) out[m[1]] = color
  }
  return out
}

/** `top` with its alpha (times `alpha`) over an opaque `under`. */
function over(top: Rgba, under: Rgba, alpha = 1): Rgba {
  const a = top[3] * alpha
  return [0, 1, 2].map((i) => top[i] * a + under[i] * (1 - a)).concat(1) as Rgba
}

const linear = (c: number) => {
  const s = c / 255
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
}

function luminance([r, g, b]: Rgba): number {
  return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)
}

function contrast(a: Rgba, b: Rgba): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number]
  return (hi + 0.05) / (lo + 0.05)
}

function oklab([r, g, b]: Rgba): [number, number, number] {
  const [lr, lg, lb] = [linear(r), linear(g), linear(b)]
  const l = Math.cbrt(0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb)
  const m = Math.cbrt(0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb)
  const s = Math.cbrt(0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb)
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ]
}

function deltaE(a: Rgba, b: Rgba): number {
  const [x, y] = [oklab(a), oklab(b)]
  return Math.hypot(x[0] - y[0], x[1] - y[1], x[2] - y[2])
}

const CLASSES = [
  'brilliant',
  'great',
  'best',
  'excellent',
  'good',
  'book',
  'inaccuracy',
  'mistake',
  'blunder',
  'miss',
]
const MODES = { dark: '@theme static', light: "[data-mode='light'] {" }

function mode(name: keyof typeof MODES) {
  const t = { ...block(MODES.dark), ...block(MODES[name]) }
  return (key: string): Rgba => {
    if (!(key in t)) throw new Error(`token --color-${key} missing`)
    return t[key]
  }
}

describe.each(Object.keys(MODES) as (keyof typeof MODES)[])('%s mode', (name) => {
  const c = mode(name)
  const t = { ...block(MODES.dark), ...block(MODES[name]) }
  /** Verdict text: its own token in light mode, the badge fill in dark (var() alias). */
  const text = (cls: string): Rgba => t[`cls-${cls}-text`] ?? c(`cls-${cls}`)

  it.each([
    ['fg', 'panel'],
    ['fg', 'bg'],
    ['muted', 'panel'],
    ['muted', 'bg'],
    ['muted', 'panel-2'],
    ['accent', 'panel'],
    ['on-accent', 'accent'],
    ['bad', 'panel'],
    ['good', 'panel'],
    ['warn', 'panel'],
  ])('%s on %s >= 4.5:1', (fg, bg) => {
    expect(contrast(c(fg), c(bg))).toBeGreaterThanOrEqual(4.5)
  })

  it.each(CLASSES)('%s: badge symbol and verdict text >= 4.5:1', (cls) => {
    expect(contrast(c('cls-ink'), c(`cls-${cls}`))).toBeGreaterThanOrEqual(4.5)
    expect(contrast(text(cls), c('panel'))).toBeGreaterThanOrEqual(4.5)
  })

  it('inaccuracy, mistake and blunder are clearly different (badges and text)', () => {
    for (const color of [(k: string) => c(`cls-${k}`), text]) {
      const [i, m, b] = ['inaccuracy', 'mistake', 'blunder'].map(color)
      expect(deltaE(i, m)).toBeGreaterThanOrEqual(0.09)
      expect(deltaE(m, b)).toBeGreaterThanOrEqual(0.09)
      expect(deltaE(i, b)).toBeGreaterThanOrEqual(0.15)
    }
  })

  it('the accent is not mistaken for an error or a classification', () => {
    for (const k of ['bad', 'warn', 'cls-great', 'cls-brilliant', 'cls-best', 'cls-miss']) {
      expect(deltaE(c('accent'), c(k)), k).toBeGreaterThanOrEqual(0.08)
    }
  })
})

/** Arrows are drawn at this opacity (ReviewBoard ARROW_OPTIONS). */
const ARROW_OPACITY = 0.8
/** Square marks: tint and ring alphas (ReviewBoard MARK_STYLES). */
const MARK_TINT = { danger: 0.35, target: 0.3, good: 0.35 }
const MARK_RING = 0.95

describe.each(BOARDS)('board %s', (board) => {
  // Brown is also the default: the other boards start from it.
  const t = { ...block("[data-board='brown'] {"), ...block(`[data-board='${board}'] {`) }
  const get = (key: string): Rgba => {
    if (!(key in t)) throw new Error(`token --color-${key} missing`)
    return t[key]
  }
  const b = (key: string) => get(`board-${key}`)
  const arrow = (key: string) => get(`arrow-${key}`)
  const squares = { light: b('light'), dark: b('dark') }

  it('coordinates >= 3:1 on their squares', () => {
    expect(contrast(b('coord-light'), squares.light)).toBeGreaterThanOrEqual(3)
    expect(contrast(b('coord-dark'), squares.dark)).toBeGreaterThanOrEqual(3)
  })

  describe.each(Object.entries(squares))('on the %s squares', (_, square) => {
    it.each([
      ['last-move', 0.08],
      ['neutral', 0.07],
      ['check', 0.18],
      ['hint', 0.2],
    ])('%s stands out', (key, min) => {
      expect(deltaE(over(b(key), square), square)).toBeGreaterThanOrEqual(min)
    })

    it('marks: tint and ring stand out and differ from each other', () => {
      const rings = (['danger', 'target', 'good'] as const).map((role) => {
        const color = b(role)
        expect(deltaE(over(color, square, MARK_TINT[role]), square), role).toBeGreaterThanOrEqual(
          0.06,
        )
        const ring = over(color, square, MARK_RING)
        expect(deltaE(ring, square), role).toBeGreaterThanOrEqual(0.15)
        return ring
      })
      for (const [x, y] of [
        [0, 1],
        [1, 2],
        [0, 2],
      ] as const) {
        expect(deltaE(rings[x], rings[y])).toBeGreaterThanOrEqual(0.12)
      }
    })

    it('arrows stand out and differ from each other', () => {
      const drawn = ['best', 'threat', 'attack'].map((key) => {
        const color = over(arrow(key), square, ARROW_OPACITY)
        expect(deltaE(color, square), key).toBeGreaterThanOrEqual(0.15)
        return color
      })
      expect(deltaE(drawn[0], drawn[1])).toBeGreaterThanOrEqual(0.15)
      expect(deltaE(drawn[1], drawn[2])).toBeGreaterThanOrEqual(0.1)
      expect(deltaE(drawn[0], drawn[2])).toBeGreaterThanOrEqual(0.1)
    })

    it('classified move target (55 %) stands out (badge fills are shared by both modes)', () => {
      const c = mode('dark')
      for (const cls of CLASSES) {
        const tinted = over(c(`cls-${cls}`), square, 0.55)
        // Book (known theory) is a quiet grey-blue: its badge says it, the tint only hints.
        const min = cls === 'book' ? 0.02 : 0.05
        expect(deltaE(tinted, square), cls).toBeGreaterThanOrEqual(min)
      }
    })
  })
})
