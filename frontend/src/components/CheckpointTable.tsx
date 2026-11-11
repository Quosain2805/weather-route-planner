import type { KeyboardEvent } from 'react'
import type { Checkpoint } from '../api/types'
import { formatEta } from '../lib/format'
import { RiskBadge } from './RiskBadge'

interface Props {
  checkpoints: Checkpoint[]
  focusedIndex: number | null
  onFocusCheckpoint: (index: number) => void
}

export function CheckpointTable({ checkpoints, focusedIndex, onFocusCheckpoint }: Props) {
  const onKey = (e: KeyboardEvent, index: number) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onFocusCheckpoint(index)
    }
  }

  return (
    <div className="table-scroll" tabIndex={0} aria-label="Checkpoints along the route">
      <table className="checkpoints">
        <thead>
          <tr>
            <th scope="col">Mile</th>
            <th scope="col">ETA</th>
            <th scope="col" className="num">Wind <small>mph</small></th>
            <th scope="col" className="num">Rain <small>in/h</small></th>
            <th scope="col" className="num">Snow <small>in/h</small></th>
            <th scope="col">Risk</th>
          </tr>
        </thead>
        <tbody>
          {checkpoints.map((cp) => (
            <tr
              key={cp.index}
              tabIndex={0}
              className={cp.index === focusedIndex ? 'is-focused' : undefined}
              onClick={() => onFocusCheckpoint(cp.index)}
              onKeyDown={(e) => onKey(e, cp.index)}
              title={cp.reason}
            >
              <td>{Math.round(cp.mile)}</td>
              <td>{formatEta(cp.eta_epoch, cp.timezone)}</td>
              <td className="num" data-level={cp.wind_risk}>{cp.wind_mph.toFixed(1)}</td>
              <td className="num" data-level={cp.rain_risk}>{cp.rain_in_hr.toFixed(2)}</td>
              <td className="num" data-level={cp.snow_risk}>{cp.snow_in_hr.toFixed(2)}</td>
              <td><RiskBadge level={cp.risk} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
