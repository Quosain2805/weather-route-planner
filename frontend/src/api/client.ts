import type { AnalyzeResponse, Place, TripRequest } from './types'

const BASE = import.meta.env.VITE_API_BASE ?? ''

export class ApiError extends Error {
  readonly code: string
  readonly status: number

  constructor(message: string, code: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, init)
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new ApiError("Can't reach the server. Check your connection and try again.", 'network', 0)
  }

  if (res.ok) return (await res.json()) as T

  let code = 'error'
  let message = `Request failed (${res.status})`
  try {
    const body = await res.json()
    code = body?.error?.code ?? code
    message = body?.error?.message ?? message
  } catch {
    /* non-JSON error page; keep the generic message */
  }
  if (res.status === 429) message = 'Too many requests. Please wait a moment and try again.'
  throw new ApiError(message, code, res.status)
}

export function analyzeTrip(trip: TripRequest, signal?: AbortSignal): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(trip),
    signal,
  })
}

export function searchPlaces(query: string, signal?: AbortSignal): Promise<Place[]> {
  return request<Place[]>(`/api/geocode?q=${encodeURIComponent(query)}`, { signal })
}
