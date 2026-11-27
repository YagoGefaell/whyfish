import type { ReactNode } from 'react'
import type { Explanation, MoveRef } from '../../api/analysis'

const MARK = /\[\[([^[\]]+)\]\]/g

/**
 * One paragraph of an explanation: text with every [[SAN]] mark turned into a clickable move.
 * `refs` are consumed in order (one per mark); `offset` is the index of the first mark.
 */
export function MarkedParagraph({
  text,
  refs,
  offset,
  onRef,
}: {
  text: string
  refs: MoveRef[]
  offset: number
  onRef: (ref: MoveRef) => void
}) {
  const parts: ReactNode[] = []
  let last = 0
  let index = offset
  for (const match of text.matchAll(MARK)) {
    const start = match.index
    if (start > last) parts.push(text.slice(last, start))
    const ref: MoveRef | undefined = index < refs.length ? refs[index] : undefined
    const san = match[1]
    parts.push(
      ref ? (
        <button
          key={start}
          type="button"
          onClick={() => {
            onRef(ref)
          }}
          title="Ver en el tablero"
          className="tabular rounded-md bg-panel-2 px-1.5 py-px font-semibold text-fg hover:bg-hover"
        >
          {san}
        </button>
      ) : (
        <strong key={start} className="tabular">
          {san}
        </strong>
      ),
    )
    index += 1
    last = start + match[0].length
  }
  if (last < text.length) parts.push(text.slice(last))
  return <p>{parts}</p>
}

interface Props {
  explanation: Explanation | null
  loading: boolean
  onRef: (ref: MoveRef) => void
}

/** The coach's explanation: level 1, or level 2 ("Profundizar") with several paragraphs. */
export function MoveExplanation({ explanation, loading, onRef }: Props) {
  if (loading && !explanation) {
    return (
      <p aria-label="Explicación" className="text-[15px] text-muted">
        Preparando la explicación…
      </p>
    )
  }
  if (!explanation?.text) return null
  const paragraphs = explanation.text.split('\n\n')
  // Index of the first mark of each paragraph (refs are in text order).
  const counts = paragraphs.map((text) => [...text.matchAll(MARK)].length)
  const offsets = counts.map((_, i) => counts.slice(0, i).reduce((a, b) => a + b, 0))
  return (
    <div
      aria-label="Explicación"
      aria-live="polite"
      className="flex flex-col gap-2 text-[15px] leading-relaxed"
    >
      {paragraphs.map((text, i) => (
        <MarkedParagraph
          key={i}
          text={text}
          refs={explanation.refs}
          offset={offsets[i] ?? 0}
          onRef={onRef}
        />
      ))}
    </div>
  )
}
