import type { DeparturePlan } from '../api/types'
import { formatSliderTime } from '../lib/format'
import { riskColor, riskLabel } from '../lib/risk'

interface Props {
  plan: DeparturePlan
  busy: boolean
  onLeaveAt: (offsetHours: number) => void
}

/**
 * "When should I leave?" For each start time in the next 48 hours, the colour is the worst
 * weather on the best route available if you set off then. Click any bar to re-plan for it.
 */
export function DeparturePlanner({ plan, busy, onLeaveAt }: Props) {
  const { options, recommended_offset_h: best } = plan
  if (options.length === 0) return null

  const first = options[0]
  const last = options[options.length - 1]
  const better = best > 0
  const target = options[best]

  return (
    <section className="planner" aria-label="Best time to leave">
      <header className="planner-head">
        <h3>Best time to leave</h3>
        <span className="planner-range">next {last.offset_h} h</span>
      </header>

      <p className={`planner-message${better ? ' is-advice' : ''}`}>{plan.message}</p>

      <div className="planner-bars" role="group" aria-label="Weather risk by departure time">
        {options.map((o) => (
          <button
            key={o.offset_h}
            type="button"
            className={`planner-bar${o.offset_h === best ? ' is-best' : ''}${o.offset_h === 0 ? ' is-now' : ''}`}
            style={{ ['--c' as string]: riskColor(o.max_risk), ['--h' as string]: `${22 + o.max_risk * 19.5}%` }}
            disabled={busy || o.offset_h === 0}
            title={`${formatSliderTime(o.epoch)}: ${riskLabel(o.max_risk)}${
              o.severe_mi + o.no_travel_mi > 0 ? ` (${o.no_travel_mi + o.severe_mi} mi Severe or worse)` : ''
            }`}
            aria-label={`Leave ${o.offset_h === 0 ? 'at the chosen time' : `${o.offset_h} hours later`}: ${riskLabel(o.max_risk)}`}
            onClick={() => onLeaveAt(o.offset_h)}
          />
        ))}
      </div>
      <div className="planner-axis">
        <span>{formatSliderTime(first.epoch)}</span>
        <span>{formatSliderTime(last.epoch)}</span>
      </div>

      {better && target && (
        <button type="button" className="planner-cta" disabled={busy} onClick={() => onLeaveAt(best)}>
          Re-plan for {formatSliderTime(target.epoch)}
          <span>+{best} h</span>
        </button>
      )}
    </section>
  )
}
