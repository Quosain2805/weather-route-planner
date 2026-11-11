import { riskLabel } from './risk'

/** Identity colours for the three route lines; deliberately distinct from the risk palette. */
const ROUTE_COLORS = ['#ffc21a', '#4cc9f0', '#c3cdd9']

export function routeColor(index: number): string {
  return ROUTE_COLORS[index % ROUTE_COLORS.length]
}

/** Mile-weighted average risk (0..4) as "1.2 · Moderate". */
export function avgRiskLabel(avg: number): string {
  return `${avg.toFixed(2)} · ${riskLabel(avg)}`
}
