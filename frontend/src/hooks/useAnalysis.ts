import { useCallback, useEffect, useRef, useState } from 'react'
import { analyzeTrip, ApiError } from '../api/client'
import type { AnalyzeResponse, TripRequest } from '../api/types'

export interface AnalysisState {
  status: 'idle' | 'loading' | 'success' | 'error'
  /** Last successful result; kept while a new request is in flight so the UI doesn't flash empty. */
  data: AnalyzeResponse | null
  error: string | null
}

export function useAnalysis() {
  const [state, setState] = useState<AnalysisState>({ status: 'idle', data: null, error: null })
  const controller = useRef<AbortController | null>(null)

  useEffect(() => () => controller.current?.abort(), [])

  const run = useCallback(async (trip: TripRequest) => {
    controller.current?.abort()
    const ctrl = new AbortController()
    controller.current = ctrl
    setState((s) => ({ ...s, status: 'loading', error: null }))
    try {
      const data = await analyzeTrip(trip, ctrl.signal)
      setState({ status: 'success', data, error: null })
      return data
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return null
      const message = err instanceof ApiError ? err.message : 'Something went wrong. Please try again.'
      setState((s) => ({ ...s, status: 'error', error: message }))
      return null
    }
  }, [])

  return { ...state, run }
}
