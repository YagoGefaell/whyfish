import type { WhiteEval } from '../../api/analysis'
import type { Color } from '../../api/games'
import { evalLabel } from './classification'

interface Props {
  evaluation: WhiteEval | null
  orientation: 'vertical' | 'horizontal'
  /** Board orientation: in the vertical bar white's share sits on white's side of the board. */
  boardOrientation: Color
  className?: string
}

/**
 * White's share of the bar = white's win%. Vertical: next to the board, white on white's side.
 * Horizontal (mobile): white grows from the left. Greyed out while there is no evaluation.
 */
export function EvalBar({ evaluation, orientation, boardOrientation, className = '' }: Props) {
  const win = evaluation?.win ?? 50
  const label = evaluation ? evalLabel(evaluation) : '…'
  const vertical = orientation === 'vertical'
  // Is white's segment at the end (bottom / right) of the bar?
  const whiteAtEnd = vertical ? boardOrientation === 'white' : false
  const share = `${String(win)}%`
  const whiteSegment = (
    <div
      className="shrink-0 bg-gray-100 transition-all duration-300"
      style={vertical ? { height: share } : { width: share }}
    />
  )
  // The label sits at the end of the side that is better.
  const labelAtEnd = win >= 50 ? whiteAtEnd : !whiteAtEnd
  const labelPlace = vertical
    ? `inset-x-0 text-center ${labelAtEnd ? 'bottom-1' : 'top-1'}`
    : `inset-y-0 flex items-center px-1 ${labelAtEnd ? 'right-0' : 'left-0'}`
  return (
    <div
      role="meter"
      aria-label="Evaluación"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(win)}
      aria-valuetext={label}
      data-testid={`eval-bar-${orientation}`}
      className={`relative flex overflow-hidden rounded bg-gray-700 ${
        vertical ? 'w-6 flex-col' : 'h-5 w-full flex-row'
      } ${evaluation ? '' : 'opacity-40'} ${className}`}
    >
      {whiteAtEnd ? <div className="flex-1" /> : whiteSegment}
      {whiteAtEnd ? whiteSegment : <div className="flex-1" />}
      <span
        className={`absolute text-[10px] font-semibold text-white mix-blend-difference ${labelPlace}`}
      >
        {label}
      </span>
    </div>
  )
}
