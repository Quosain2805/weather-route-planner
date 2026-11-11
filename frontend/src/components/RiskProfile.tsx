import type { Checkpoint } from '../api/types'
import { riskColor, riskLabel } from '../lib/risk'

interface Props {
  checkpoints: Checkpoint[]
  totalMiles: number
  focusedIndex: number | null
  onFocusCheckpoint: (index: number) => void
}

/**
 * The route as a strip of bars, one per checkpoint. Width is the stretch of road that checkpoint
 * speaks for, height and colour are its risk, so you can see *where* along the trip it turns bad.
 */
export function RiskProfile({ checkpoints, totalMiles, focusedIndex, onFocusCheckpoint }: Props) {
  return (
    <figure className="profile">
      <div className="profile-bars" role="img" aria-label="Weather risk along the route, origin to destination">
        {checkpoints.map((cp) => (
          <button
            key={cp.index}
            type="button"
            className={`profile-bar${cp.index === focusedIndex ? ' is-focused' : ''}`}
            style={{
              flexGrow: Math.max(cp.covered_miles, 0.01),
              ['--h' as string]: `${18 + cp.risk * 20.5}%`,
              ['--c' as string]: riskColor(cp.risk),
            }}
            title={`Mile ${Math.round(cp.mile)} · ${riskLabel(cp.risk)}`}
            aria-label={`Mile ${Math.round(cp.mile)}, ${riskLabel(cp.risk)}`}
            onClick={() => onFocusCheckpoint(cp.index)}
          />
        ))}
      </div>
      <figcaption className="profile-axis">
        <span>Origin</span>
        <span>{Math.round(totalMiles / 2).toLocaleString('en-US')} mi</span>
        <span>{Math.round(totalMiles).toLocaleString('en-US')} mi</span>
      </figcaption>
    </figure>
  )
}
