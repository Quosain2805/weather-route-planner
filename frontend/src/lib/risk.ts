import type { RiskLevel } from '../api/types'

export const RISK_LABELS = ['Low', 'Moderate', 'High', 'Severe', 'No Travel'] as const

/** Keep in sync with the --risk-* custom properties in styles.css. */
export const RISK_COLORS = ['#35d07f', '#ffd23f', '#ff9f1a', '#ff4d4d', '#b46bff'] as const

export const MILE_KEYS = ['low', 'moderate', 'high', 'severe', 'no_travel'] as const

export function riskLabel(level: number): string {
  return RISK_LABELS[clampLevel(level)]
}

export function riskColor(level: number): string {
  return RISK_COLORS[clampLevel(level)]
}

export function clampLevel(level: number): RiskLevel {
  return Math.max(0, Math.min(4, Math.round(level))) as RiskLevel
}
