import { riskLabel } from '../lib/risk'

export function RiskBadge({ level }: { level: number }) {
  return (
    <span className="badge" data-level={level}>
      {riskLabel(level)}
    </span>
  )
}
