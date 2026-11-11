import L from 'leaflet'
import { useEffect, useMemo } from 'react'
import { CircleMarker, MapContainer, Marker, Pane, Polyline, Popup, TileLayer, Tooltip, ZoomControl, useMap } from 'react-leaflet'
import type { AnalyzeResponse, Checkpoint, RouteResult } from '../api/types'
import { formatEta } from '../lib/format'
import type { HeatMetric } from '../lib/heat'
import { riskColor, riskLabel } from '../lib/risk'
import { routeColor } from '../lib/routes'
import { HeatOverlay } from './HeatOverlay'

interface Props {
  data: AnalyzeResponse | null
  selectedId: string | null
  focusedCheckpoint: number | null
  onSelectRoute: (id: string) => void
  onFocusCheckpoint: (index: number | null) => void
  heat: { metric: HeatMetric; hour: number; visible: boolean }
}

const US_CENTER: L.LatLngTuple = [39.5, -96.5]
const SIDEBAR_PX = 440
const NO_ROUTES: RouteResult[] = []

const colorIndex = (route: RouteResult) => Number(route.id.slice(1)) - 1

function pinIcon(letter: string, tone: 'start' | 'end') {
  return L.divIcon({
    className: 'pin-wrap',
    html: `<span class="pin pin-${tone}">${letter}</span>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  })
}
const START_ICON = pinIcon('A', 'start')
const END_ICON = pinIcon('B', 'end')

function FitToRoutes({ data }: { data: AnalyzeResponse | null }) {
  const map = useMap()
  useEffect(() => {
    if (!data) return
    const bounds = L.latLngBounds(data.routes.flatMap((r) => r.geometry))
    if (!bounds.isValid()) return
    // On wide screens the trip panel floats over the left of the map and the forecast dock over the bottom.
    const wide = window.innerWidth >= 1000
    map.fitBounds(bounds, {
      paddingTopLeft: wide ? [SIDEBAR_PX + 64, 56] : [28, 28],
      paddingBottomRight: wide ? [56, 210] : [28, 28],
      maxZoom: 11,
    })
  }, [data, map])
  return null
}

function FlyToCheckpoint({ checkpoint }: { checkpoint: Checkpoint | null }) {
  const map = useMap()
  useEffect(() => {
    if (checkpoint) map.flyTo([checkpoint.lat, checkpoint.lon], Math.max(map.getZoom(), 8), { duration: 0.6 })
  }, [checkpoint, map])
  return null
}

export function MapView({ data, selectedId, focusedCheckpoint, onSelectRoute, onFocusCheckpoint, heat }: Props) {
  const routes = data?.routes ?? NO_ROUTES
  const selected = routes.find((r) => r.id === selectedId) ?? null
  const focused = selected && focusedCheckpoint !== null ? (selected.checkpoints[focusedCheckpoint] ?? null) : null

  // The recommended route's endpoints are the snapped trip start and end.
  const ends = useMemo(() => {
    const g = routes[0]?.geometry
    return g && g.length > 1 ? { start: g[0], end: g[g.length - 1] } : null
  }, [routes])

  return (
    <MapContainer center={US_CENTER} zoom={4} minZoom={3} zoomControl={false} zoomSnap={0.25} zoomDelta={0.5} className="map" worldCopyJump>
      <TileLayer
        url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
        maxNativeZoom={16}
        maxZoom={18}
        attribution="Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors"
      />
      {/* Place names sit above the heatmap but below the route lines. */}
      <Pane name="labels" style={{ zIndex: 360, pointerEvents: 'none' }}>
        <TileLayer
          url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}"
          maxNativeZoom={16}
          maxZoom={18}
        />
      </Pane>
      <ZoomControl position="topright" />
      <FitToRoutes data={data} />
      <FlyToCheckpoint checkpoint={focused} />

      {data && <HeatOverlay heatmap={data.heatmap} metric={heat.metric} hour={heat.hour} visible={heat.visible} />}

      <Pane name="routes-muted" style={{ zIndex: 410 }} />
      <Pane name="routes-active" style={{ zIndex: 420 }} />
      <Pane name="checkpoints" style={{ zIndex: 430 }} />

      {routes.map((route) => {
        const isSelected = route.id === selectedId
        return (
          <RouteLine key={`${route.id}-${isSelected}`} route={route} selected={isSelected} onSelect={() => onSelectRoute(route.id)} />
        )
      })}

      {selected?.checkpoints.map((cp) => (
        <CircleMarker
          key={cp.index}
          center={[cp.lat, cp.lon]}
          radius={6}
          pane="checkpoints"
          pathOptions={{ color: '#0b0f14', weight: 2.5, fillColor: riskColor(cp.risk), fillOpacity: 1 }}
          eventHandlers={{ click: () => onFocusCheckpoint(cp.index) }}
        >
          <Tooltip direction="top" offset={[0, -6]}>
            <CheckpointSummary cp={cp} />
          </Tooltip>
        </CircleMarker>
      ))}

      {focused && (
        <>
          <CircleMarker
            center={[focused.lat, focused.lon]}
            radius={12}
            pane="checkpoints"
            interactive={false}
            pathOptions={{ color: '#ffffff', weight: 2.5, fill: false }}
          />
          <Popup position={[focused.lat, focused.lon]} offset={[0, -10]} eventHandlers={{ remove: () => onFocusCheckpoint(null) }}>
            <CheckpointSummary cp={focused} detailed />
          </Popup>
        </>
      )}

      {ends && (
        <>
          <Marker position={ends.start} icon={START_ICON} keyboard={false} interactive={false} zIndexOffset={1000} />
          <Marker position={ends.end} icon={END_ICON} keyboard={false} interactive={false} zIndexOffset={1000} />
        </>
      )}
    </MapContainer>
  )
}

function RouteLine({ route, selected, onSelect }: { route: RouteResult; selected: boolean; onSelect: () => void }) {
  const color = routeColor(colorIndex(route))
  return (
    <>
      {selected && (
        <>
          <Polyline
            positions={route.geometry}
            pane="routes-active"
            interactive={false}
            pathOptions={{ color, weight: 18, opacity: 0.16, lineCap: 'round', lineJoin: 'round' }}
          />
          <Polyline
            positions={route.geometry}
            pane="routes-active"
            interactive={false}
            pathOptions={{ color: '#0b0f14', weight: 9, opacity: 0.95, lineCap: 'round', lineJoin: 'round' }}
          />
        </>
      )}
      <Polyline
        positions={route.geometry}
        pane={selected ? 'routes-active' : 'routes-muted'}
        pathOptions={{
          color,
          weight: selected ? 4.5 : 3,
          opacity: selected ? 1 : 0.8,
          dashArray: selected ? undefined : '2 8',
          lineCap: 'round',
          lineJoin: 'round',
        }}
        eventHandlers={{ click: onSelect }}
      >
        {!selected && <Tooltip sticky>{`${route.name} — click to select`}</Tooltip>}
      </Polyline>
    </>
  )
}

function CheckpointSummary({ cp, detailed = false }: { cp: Checkpoint; detailed?: boolean }) {
  return (
    <div className="cp-summary">
      <strong>
        Mile {Math.round(cp.mile)} · {riskLabel(cp.risk)}
      </strong>
      <span>{formatEta(cp.eta_epoch, cp.timezone)}</span>
      <span>
        Wind {cp.wind_mph.toFixed(1)} mph · Rain {cp.rain_in_hr.toFixed(2)} in/hr · Snow {cp.snow_in_hr.toFixed(2)} in/hr
      </span>
      {detailed && <em>{cp.reason}</em>}
    </div>
  )
}
