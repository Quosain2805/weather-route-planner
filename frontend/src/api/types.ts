/** Shapes returned by the Django API. Risk levels are 0 (Low) .. 4 (No Travel). */

export type RiskLevel = 0 | 1 | 2 | 3 | 4

export interface Place {
  label: string
  lat: number
  lon: number
}

export interface TripRequest {
  origin: Place
  destination: Place
  /** ISO 8601, UTC */
  departure: string
  load_lb: number
  interval_miles: number
}

export interface Checkpoint {
  index: number
  mile: number
  covered_miles: number
  lat: number
  lon: number
  eta_epoch: number
  timezone: string
  wind_mph: number
  rain_in_hr: number
  snow_in_hr: number
  risk: RiskLevel
  wind_risk: RiskLevel
  rain_risk: RiskLevel
  snow_risk: RiskLevel
  reason: string
}

export interface RouteSummary {
  max_risk: RiskLevel
  avg_risk: number
  miles_by_risk: Record<'low' | 'moderate' | 'high' | 'severe' | 'no_travel', number>
}

export interface RouteResult {
  id: string
  name: string
  via: string
  rank: number
  recommended: boolean
  fastest: boolean
  distance_mi: number
  duration_s: number
  extra_s_vs_fastest: number
  departure_epoch: number
  arrival_epoch: number
  summary: RouteSummary
  reasons: string[]
  geometry: [number, number][]
  checkpoints: Checkpoint[]
}

export interface HeatPoint {
  lat: number
  lon: number
  wind: number[]
  rain: number[]
  snow: number[]
  risk: number[]
}

export interface Heatmap {
  start_epoch: number
  hours: number
  spacing_mi: number
  /** Lower bounds of Moderate, High, Severe, No Travel for each hazard */
  scales: Record<'wind' | 'rain' | 'snow', number[]>
  points: HeatPoint[]
}

export interface DepartureOption {
  offset_h: number
  epoch: number
  best_route_id: string
  max_risk: RiskLevel
  avg_risk: number
  no_travel_mi: number
  severe_mi: number
  high_mi: number
}

export interface DeparturePlan {
  recommended_offset_h: number
  message: string
  /** The best route's outcome for each start time, hour by hour from the requested departure. */
  options: DepartureOption[]
}

export interface AnalyzeResponse {
  recommended_route_id: string
  interval_mi: number
  warnings: string[]
  routes: RouteResult[]
  departure_plan: DeparturePlan
  heatmap: Heatmap
}
