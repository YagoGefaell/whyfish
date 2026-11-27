import type { CSSProperties } from 'react'
import type { Classification } from '../api/analysis'
import { CLASSIFICATIONS } from '../features/review/classification'

/**
 * Classification badge: a rounded square in the classification colour with the symbol drawn
 * in SVG (no emoji, no font glyph for the icons). Punctuation marks (!!, !, ?!, ?, ??) are SVG
 * text. Colours are tokens (--color-cls-*), set as styles because SVG presentation attributes
 * do not resolve `var()`.
 */
export function ClassBadge({
  classification,
  size = 20,
  className = '',
}: {
  classification: Classification
  size?: number
  className?: string
}) {
  const meta = CLASSIFICATIONS[classification]
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      role="img"
      aria-label={meta.label}
      className={`shrink-0 ${className}`}
      data-classification={classification}
    >
      <title>{meta.label}</title>
      <rect
        x="1"
        y="1"
        width="22"
        height="22"
        rx="6"
        style={{ fill: meta.color, stroke: 'var(--color-cls-outline)', strokeWidth: 1 }}
      />
      <Symbol classification={classification} />
    </svg>
  )
}

const INK = 'var(--color-cls-ink)'

const STROKE: CSSProperties = {
  fill: 'none',
  stroke: INK,
  strokeWidth: 2.4,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
}

function Mark({ text }: { text: string }) {
  return (
    <text
      x="12"
      y="12.5"
      textAnchor="middle"
      dominantBaseline="central"
      fontSize={text.length > 1 ? 11.5 : 14}
      fontWeight={800}
      letterSpacing={text.length > 1 ? -1 : 0}
      style={{ fill: INK, fontFamily: 'var(--font-sans)' }}
    >
      {text}
    </text>
  )
}

function Symbol({ classification }: { classification: Classification }) {
  switch (classification) {
    case 'brilliant':
      return <Mark text="!!" />
    case 'great':
      return <Mark text="!" />
    case 'inaccuracy':
      return <Mark text="?!" />
    case 'mistake':
      return <Mark text="?" />
    case 'blunder':
      return <Mark text="??" />
    case 'best':
      // A cut gem (own icon): the best move.
      return (
        <g style={{ ...STROKE, strokeWidth: 1.7 }}>
          <path d="M8.2 6.5h7.6l3 3.6L12 18.2 5.2 10.1z" style={{ fill: INK, stroke: INK }} />
          <path
            d="M5.4 10.1h13.2M10 6.7l-1.2 3.4L12 17.6l3.2-7.5L14 6.7"
            style={{ ...STROKE, strokeWidth: 0.9, stroke: 'var(--color-cls-best)' }}
          />
        </g>
      )
    case 'excellent':
      // Thumbs up.
      return (
        <g style={{ ...STROKE, strokeWidth: 1.9 }}>
          <path d="M9.5 17.5H7a1 1 0 0 1-1-1v-5a1 1 0 0 1 1-1h2.5" />
          <path d="M9.5 10.5l2.4-4.3a1.3 1.3 0 0 1 2.4.8l-.5 2.6h3.2a1.5 1.5 0 0 1 1.5 1.8l-1 5a1.5 1.5 0 0 1-1.5 1.1H9.5z" />
        </g>
      )
    case 'good':
      return <path d="M7.5 12.5l3 3 6-6.5" style={STROKE} />
    case 'book':
      // A bookmark ribbon over text lines (own icon): known theory.
      return (
        <g style={{ ...STROKE, strokeWidth: 1.7 }}>
          <path d="M6.5 8h4M6.5 11.5h4M6.5 15h11" />
          <path
            d="M13.5 6.2h4v7l-2-1.6-2 1.6z"
            style={{ fill: INK, stroke: INK, strokeWidth: 1.2 }}
          />
        </g>
      )
    case 'miss':
      return <path d="M8.2 8.2l7.6 7.6M15.8 8.2l-7.6 7.6" style={STROKE} />
  }
}
