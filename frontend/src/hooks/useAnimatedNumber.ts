import { useEffect, useRef, useState } from 'react'

const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3)

const prefersReducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false

/** Eases toward `target` over `durationMs`. Used so the heatmap glides between forecast hours. */
export function useAnimatedNumber(target: number, durationMs = 380): number {
  const [value, setValue] = useState(target)
  const current = useRef(target)
  const [reduced] = useState(prefersReducedMotion)
  const instant = reduced || durationMs <= 0

  useEffect(() => {
    if (instant) return

    const from = current.current
    const start = performance.now()
    let frame = 0
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs)
      current.current = from + (target - from) * easeOutCubic(t)
      setValue(current.current)
      if (t < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, durationMs, instant])

  return instant ? target : value
}
