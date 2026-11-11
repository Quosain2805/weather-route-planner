import type { Heatmap, HeatPoint } from '../api/types'
import { RISK_COLORS } from './risk'

export type HeatMetric = 'risk' | 'wind' | 'rain' | 'snow'

export const METRIC_LABELS: Record<HeatMetric, string> = {
  risk: 'Overall risk',
  wind: 'Wind',
  rain: 'Rain',
  snow: 'Snow',
}

/** Linear interpolation of an hourly series at a fractional hour (clamped to the series). */
export function valueAt(series: number[], hour: number): number {
  if (series.length === 0) return 0
  const h = Math.max(0, Math.min(series.length - 1, hour))
  const lo = Math.floor(h)
  const hi = Math.min(series.length - 1, lo + 1)
  return series[lo] + (series[hi] - series[lo]) * (h - lo)
}

/**
 * Position on the 0..4 colour scale (Low..No Travel) for a metric value.
 * Hazard values map piecewise-linearly through the server's own thresholds, so a colour on the
 * map means the same thing as the band named in the route table.
 */
export function scalePosition(metric: HeatMetric, value: number, scales: Heatmap['scales']): number {
  if (metric === 'risk') return Math.max(0, Math.min(4, value))
  const bounds = scales[metric]
  if (value <= 0) return 0
  let lower = 0
  for (let i = 0; i < bounds.length; i++) {
    if (value < bounds[i]) return i + (value - lower) / (bounds[i] - lower)
    lower = bounds[i]
  }
  return 4
}

export function pointPosition(point: HeatPoint, metric: HeatMetric, hour: number, scales: Heatmap['scales']): number {
  return scalePosition(metric, valueAt(point[metric], hour), scales)
}

const STOPS = RISK_COLORS.map((hex) => [
  parseInt(hex.slice(1, 3), 16),
  parseInt(hex.slice(3, 5), 16),
  parseInt(hex.slice(5, 7), 16),
]) as [number, number, number][]

/** Colour at a position on the 0..4 scale, blended between the risk colours. */
export function colorAt(position: number): [number, number, number] {
  const p = Math.max(0, Math.min(4, position))
  const lo = Math.floor(p)
  const hi = Math.min(4, lo + 1)
  const f = p - lo
  return [0, 1, 2].map((c) => Math.round(STOPS[lo][c] + (STOPS[hi][c] - STOPS[lo][c]) * f)) as [
    number,
    number,
    number,
  ]
}

export function legendGradient(): string {
  const stops = RISK_COLORS.map((c, i) => `${c} ${(i / 4) * 100}%`).join(', ')
  return `linear-gradient(90deg, ${stops})`
}

export function metricUnit(metric: HeatMetric): string {
  return { risk: '', wind: 'mph', rain: 'in/hr', snow: 'in/hr' }[metric]
}

/** Tick labels under the legend gradient, one per colour stop. */
export function legendTicks(metric: HeatMetric, scales: Heatmap['scales']): string[] {
  if (metric === 'risk') return ['Low', 'Moderate', 'High', 'Severe', 'No Travel']
  const fmt = (v: number) => (metric === 'wind' ? String(v) : v.toFixed(v < 1 ? 2 : 1))
  const bounds = scales[metric]
  return ['0', ...bounds.slice(0, 3).map(fmt), `${fmt(bounds[3])}+`]
}
