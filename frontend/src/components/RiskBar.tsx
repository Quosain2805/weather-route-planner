import type { RouteSummary } from '../api/types'
import { MILE_KEYS, RISK_LABELS } from '../lib/risk'

/** Stacked bar showing how many route miles fall in each risk band. */
export function RiskBar({ miles }: { miles: RouteSummary['miles_by_risk'] }) {
  const total = MILE_KEYS.reduce((sum, k) => sum + miles[k], 0) || 1
  const worse = MILE_KEYS.map((k, level) => ({ level, miles: miles[k] })).filter((s) => s.level > 0 && s.miles >= 0.5)

  const description = MILE_KEYS.map((k, i) => `${Math.round(miles[k])} miles ${RISK_LABELS[i]}`).join(', ')

  return (
    <div>
      <div className="risk-bar" role="img" aria-label={description}>
        {MILE_KEYS.map((k, level) =>
          miles[k] > 0 ? (
            <span key={k} data-level={level} style={{ width: `${(miles[k] / total) * 100}%` }} title={`${Math.round(miles[k])} mi ${RISK_LABELS[level]}`} />
          ) : null,
        )}
      </div>
      <p className="risk-bar-caption">
        {worse.length === 0
          ? 'Low risk the whole way'
          : worse.map((s) => `${Math.round(s.miles)} mi ${RISK_LABELS[s.level]}`).join(' · ')}
      </p>
    </div>
  )
}
