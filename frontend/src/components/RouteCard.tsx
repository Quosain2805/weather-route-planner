import type { RouteResult } from '../api/types'
import { formatDelta, formatDuration, formatEta } from '../lib/format'
import { avgRiskLabel, routeColor } from '../lib/routes'
import { CheckpointTable } from './CheckpointTable'
import { RiskBadge } from './RiskBadge'
import { RiskBar } from './RiskBar'
import { RiskProfile } from './RiskProfile'

interface Props {
  route: RouteResult
  colorIndex: number
  selected: boolean
  focusedCheckpoint: number | null
  onSelect: () => void
  onFocusCheckpoint: (index: number) => void
}

export function RouteCard({ route, colorIndex, selected, focusedCheckpoint, onSelect, onFocusCheckpoint }: Props) {
  const last = route.checkpoints[route.checkpoints.length - 1]

  return (
    <article
      className={`route-card${selected ? ' is-selected' : ''}${route.recommended ? ' is-recommended' : ''}`}
      style={{ ['--route' as string]: routeColor(colorIndex) }}
      aria-current={selected ? 'true' : undefined}
    >
      <button type="button" className="route-head" onClick={onSelect} aria-expanded={selected}>
        <span className="route-rank" aria-label={`Rank ${route.rank}`}>
          {route.rank}
        </span>
        <span className="route-title">
          <strong>
            <span className="route-name">{route.via || route.name}</span>
            <i className="route-swatch" aria-hidden="true" />
          </strong>
          <span className="route-sub">
            <span className="route-via">{route.name}</span>
            {route.recommended && <span className="tag tag-recommended">Recommended</span>}
            {route.fastest && <span className="tag">Fastest</span>}
          </span>
        </span>
      </button>

      <dl className="metrics">
        <div>
          <dt>Distance</dt>
          <dd>
            {Math.round(route.distance_mi).toLocaleString('en-US')}
            <small> mi</small>
          </dd>
        </div>
        <div>
          <dt>Drive time</dt>
          <dd>{formatDuration(route.duration_s)}</dd>
          {!route.fastest && <small className="delta">{formatDelta(route.extra_s_vs_fastest)}</small>}
        </div>
        <div>
          <dt>Arrive</dt>
          <dd>{formatEta(route.arrival_epoch, last?.timezone)}</dd>
        </div>
        <div>
          <dt>Worst risk</dt>
          <dd>
            <RiskBadge level={route.summary.max_risk} />
          </dd>
        </div>
        <div>
          <dt>Avg risk</dt>
          <dd>{avgRiskLabel(route.summary.avg_risk)}</dd>
        </div>
      </dl>

      <RiskBar miles={route.summary.miles_by_risk} />

      {route.reasons.length > 0 && (
        <ul className="reasons">
          {route.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}

      {selected && (
        <>
          <section className="profile-section">
            <h3>Risk along the road</h3>
            <RiskProfile
              checkpoints={route.checkpoints}
              totalMiles={route.distance_mi}
              focusedIndex={focusedCheckpoint}
              onFocusCheckpoint={onFocusCheckpoint}
            />
          </section>
          <section className="checkpoint-section">
            <h3>
              Checkpoints <span>{route.checkpoints.length}</span>
            </h3>
            <CheckpointTable
              checkpoints={route.checkpoints}
              focusedIndex={focusedCheckpoint}
              onFocusCheckpoint={onFocusCheckpoint}
            />
          </section>
        </>
      )}
    </article>
  )
}
