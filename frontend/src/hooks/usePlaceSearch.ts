import { useEffect, useState } from 'react'
import { searchPlaces } from '../api/client'
import type { Place } from '../api/types'

const DEBOUNCE_MS = 300
const MIN_CHARS = 3

interface Settled {
  query: string
  places: Place[]
  failed: boolean
}

/**
 * Debounced, cancellable place search. Pass enabled=false to pause (e.g. once a place is chosen).
 *
 * Results are stored together with the query they answer, so a stale response can never be shown
 * for newer text and "loading" is simply "no answer for the current text yet".
 */
export function usePlaceSearch(query: string, enabled: boolean) {
  const q = query.trim()
  const active = enabled && q.length >= MIN_CHARS
  const [settled, setSettled] = useState<Settled | null>(null)

  useEffect(() => {
    if (!active) return
    const ctrl = new AbortController()
    const timer = window.setTimeout(async () => {
      try {
        const places = await searchPlaces(q, ctrl.signal)
        setSettled({ query: q, places, failed: false })
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return
        setSettled({ query: q, places: [], failed: true })
      }
    }, DEBOUNCE_MS)

    return () => {
      window.clearTimeout(timer)
      ctrl.abort()
    }
  }, [q, active])

  const current = active && settled?.query === q ? settled : null
  return {
    results: current?.places ?? [],
    loading: active && current === null,
    failed: current?.failed ?? false,
  }
}
