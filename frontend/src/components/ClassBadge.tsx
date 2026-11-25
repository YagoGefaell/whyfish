import type { Classification } from '../api/analysis'
import { CLASSIFICATIONS } from '../features/review/classification'

/**
 * Classification badge: a coloured circle with the symbol drawn in SVG (no emoji, no font
 * glyph for the icons). Punctuation marks are SVG text in the app's font.
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
      <circle cx="12" cy="12" r="11" fill={meta.color} stroke="rgba(0,0,0,0.35)" strokeWidth="1" />
      <Symbol classification={classification} />
    </svg>
  )
}

const STROKE = {
  fill: 'none',
  stroke: '#fff',
  strokeWidth: 2.4,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
} as const

function Mark({ text }: { text: string }) {
  return (
    <text
      x="12"
      y="12.5"
      textAnchor="middle"
      dominantBaseline="central"
      fill="#fff"
      fontSize={text.length > 1 ? 11.5 : 14}
      fontWeight={800}
      fontFamily="'Inter Variable', ui-sans-serif, sans-serif"
      letterSpacing={text.length > 1 ? -1 : 0}
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
      // Five-pointed star.
      return (
        <path
          d="M12 5.2l2.02 4.1 4.53.66-3.28 3.2.77 4.5L12 15.53l-4.04 2.13.77-4.5-3.28-3.2 4.53-.66z"
          fill="#fff"
        />
      )
    case 'excellent':
      // Thumbs up.
      return (
        <g {...STROKE} strokeWidth={1.9}>
          <path d="M9.5 17.5H7a1 1 0 0 1-1-1v-5a1 1 0 0 1 1-1h2.5" />
          <path d="M9.5 10.5l2.4-4.3a1.3 1.3 0 0 1 2.4.8l-.5 2.6h3.2a1.5 1.5 0 0 1 1.5 1.8l-1 5a1.5 1.5 0 0 1-1.5 1.1H9.5z" />
        </g>
      )
    case 'good':
      return <path d="M7.5 12.5l3 3 6-6.5" {...STROKE} />
    case 'book':
      // Open book.
      return (
        <g {...STROKE} strokeWidth={1.7}>
          <path d="M12 8.2c-1.6-1.2-3.6-1.5-5.5-1.2v9.3c1.9-.3 3.9 0 5.5 1.2 1.6-1.2 3.6-1.5 5.5-1.2V7c-1.9-.3-3.9 0-5.5 1.2z" />
          <path d="M12 8.2v9.3" />
        </g>
      )
    case 'miss':
      return <path d="M8.2 8.2l7.6 7.6M15.8 8.2l-7.6 7.6" {...STROKE} />
  }
}
