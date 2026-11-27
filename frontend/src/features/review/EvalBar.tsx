import type { WhiteEval } from '../../api/analysis'
import type { Color } from '../../api/games'
import { evalLabel } from './classification'

interface Props {
  evaluation: WhiteEval | null
  orientation: 'vertical' | 'horizontal'
  /** The bar turns with the board: white's share sits on white's side. */
  boardOrientation: Color
  className?: string
}

/** White's share of the bar = white's win%. Dimmed while there is no evaluation. */
export function EvalBar({ evaluation, orientation, boardOrientation, className = '' }: Props) {
  const win = evaluation?.win ?? 50
  const label = evaluation ? evalLabel(evaluation) : ''
  const vertical = orientation === 'vertical'
  // Vertical: white at the bottom when white plays from the bottom.
  // Horizontal: white on the left when white plays from the bottom.
  const whiteAtEnd = vertical ? boardOrientation === 'white' : boardOrientation === 'black'
  const share = `${String(win)}%`
  const white = (
    <div
      className="shrink-0 bg-eval-white transition-all duration-300"
      style={vertical ? { height: share } : { width: share }}
    />
  )
  const filler = <div className="flex-1" />
  const labelAtEnd = win >= 50 ? whiteAtEnd : !whiteAtEnd
  const labelColor = win >= 50 ? 'text-eval-ink' : 'text-eval-white'
  const place = vertical
    ? `inset-x-0 text-center ${labelAtEnd ? 'bottom-1' : 'top-1'}`
    : `inset-y-0 flex items-center px-1.5 ${labelAtEnd ? 'right-0' : 'left-0'}`
  return (
    <div
      role="meter"
      aria-label="Evaluación"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(win)}
      aria-valuetext={label || 'sin evaluación'}
      data-testid={`eval-bar-${orientation}`}
      className={`relative flex overflow-hidden rounded-md bg-eval-track ${
        vertical ? 'w-7 flex-col' : 'h-6 w-full flex-row'
      } ${evaluation ? '' : 'opacity-50'} ${className}`}
    >
      {whiteAtEnd ? filler : white}
      {whiteAtEnd ? white : filler}
      <span className={`tabular absolute text-[11px] font-bold ${labelColor} ${place}`}>
        {label}
      </span>
    </div>
  )
}
