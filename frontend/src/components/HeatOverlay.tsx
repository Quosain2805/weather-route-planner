import L from 'leaflet'
import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'
import type { Heatmap } from '../api/types'
import { colorAt, pointPosition } from '../lib/heat'
import type { HeatMetric } from '../lib/heat'

interface Props {
  heatmap: Heatmap
  metric: HeatMetric
  /** Fractional hours after the heatmap's start; values are interpolated between forecast hours. */
  hour: number
  visible: boolean
}

const PANE = 'heat'
const METERS_PER_MILE = 1609.344
const EARTH_CIRCUMFERENCE_M = 40075016.686
const MIN_RADIUS_PX = 10
const MAX_RADIUS_PX = 150

/**
 * Corridor heatmap drawn on a viewport-sized canvas.
 *
 * Each forecast point is a soft blob coloured by its risk (not summed density, which would hide
 * the difference between "many mild points" and "one severe point"). Blobs are drawn from least
 * to most severe so the worst conditions always sit on top. Radius follows the map scale so the
 * corridor stays continuous at every zoom.
 */
export function HeatOverlay({ heatmap, metric, hour, visible }: Props) {
  const map = useMap()
  const latest = useRef({ heatmap, metric, hour, visible })
  const redraw = useRef<() => void>(() => {})

  useEffect(() => {
    const pane = map.getPane(PANE) ?? map.createPane(PANE)
    pane.style.zIndex = '350'
    pane.style.pointerEvents = 'none'

    const canvas = L.DomUtil.create('canvas', 'heat-canvas', pane)
    const ctx = canvas.getContext('2d')
    let frame = 0

    const draw = () => {
      frame = 0
      if (!ctx) return
      const { heatmap: hm, metric: m, hour: h, visible: show } = latest.current
      const size = map.getSize()
      if (canvas.width !== size.x || canvas.height !== size.y) {
        canvas.width = size.x
        canvas.height = size.y
      }
      L.DomUtil.setPosition(canvas, map.containerPointToLayerPoint([0, 0]))
      ctx.clearRect(0, 0, size.x, size.y)
      if (!show) return

      const zoom = map.getZoom()
      const radiusM = Math.max(hm.spacing_mi, 12) * METERS_PER_MILE * 0.85

      const blobs: { x: number; y: number; r: number; pos: number }[] = []
      for (const p of hm.points) {
        const at = map.latLngToContainerPoint([p.lat, p.lon])
        const metersPerPx = (EARTH_CIRCUMFERENCE_M * Math.cos((p.lat * Math.PI) / 180)) / (256 * 2 ** zoom)
        const r = Math.max(MIN_RADIUS_PX, Math.min(MAX_RADIUS_PX, radiusM / metersPerPx))
        if (at.x < -r || at.y < -r || at.x > size.x + r || at.y > size.y + r) continue
        blobs.push({ x: at.x, y: at.y, r, pos: pointPosition(p, m, h, hm.scales) })
      }
      blobs.sort((a, b) => a.pos - b.pos)

      for (const b of blobs) {
        const [cr, cg, cb] = colorAt(b.pos)
        const grad = ctx.createRadialGradient(b.x, b.y, 0, b.x, b.y, b.r)
        grad.addColorStop(0, `rgba(${cr},${cg},${cb},0.8)`)
        grad.addColorStop(0.55, `rgba(${cr},${cg},${cb},0.55)`)
        grad.addColorStop(1, `rgba(${cr},${cg},${cb},0)`)
        ctx.fillStyle = grad
        ctx.beginPath()
        ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2)
        ctx.fill()
      }
    }

    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(draw)
    }
    redraw.current = schedule

    // Leaflet scales tile layers during a zoom animation but not a custom canvas, so fade it out.
    const hide = () => (canvas.style.opacity = '0')
    const show = () => {
      schedule()
      canvas.style.opacity = '1'
    }
    map.on('move resize viewreset', schedule)
    map.on('zoomstart', hide)
    map.on('zoomend', show)
    schedule()

    return () => {
      map.off('move resize viewreset', schedule)
      map.off('zoomstart', hide)
      map.off('zoomend', show)
      cancelAnimationFrame(frame)
      canvas.remove()
      redraw.current = () => {}
    }
  }, [map])

  useEffect(() => {
    latest.current = { heatmap, metric, hour, visible }
    redraw.current()
  }, [heatmap, metric, hour, visible])

  return null
}
