import { useEffect, useMemo, useState } from 'react'
import type { AnalyzeResponse, TripRequest } from './api/types'
import { DeparturePlanner } from './components/DeparturePlanner'
import { ForecastPanel } from './components/ForecastPanel'
import { MapView } from './components/MapView'
import { RouteCard } from './components/RouteCard'
import { TripForm } from './components/TripForm'
import { useAnalysis } from './hooks/useAnalysis'
import { useAnimatedNumber } from './hooks/useAnimatedNumber'
import { toLocalInputValue } from './lib/format'
import type { HeatMetric } from './lib/heat'

const PLAY_INTERVAL_MS = 900

export default function App() {
  const analysis = useAnalysis()
  const { data, status, error } = analysis
  const busy = status === 'loading'

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [focusedCheckpoint, setFocusedCheckpoint] = useState<number | null>(null)

  const [metric, setMetric] = useState<HeatMetric>('risk')
  const [showHeat, setShowHeat] = useState(true)
  const [targetHour, setTargetHour] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [lastTrip, setLastTrip] = useState<TripRequest | null>(null)
  const [syncDeparture, setSyncDeparture] = useState<{ value: string } | null>(null)
  const hour = useAnimatedNumber(targetHour)

  // A fresh result resets the view to the recommended route at departure time.
  const [shownData, setShownData] = useState<AnalyzeResponse | null>(null)
  if (data && data !== shownData) {
    setShownData(data)
    setSelectedId(data.recommended_route_id)
    setFocusedCheckpoint(null)
    setTargetHour(0)
    setPlaying(false)
  }

  useEffect(() => {
    if (!playing || !data) return
    const max = data.heatmap.hours
    const timer = window.setInterval(() => setTargetHour((h) => (h >= max ? 0 : h + 1)), PLAY_INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [playing, data])

  const selectRoute = (id: string) => {
    setSelectedId(id)
    setFocusedCheckpoint(null)
  }

  const submit = (trip: TripRequest) => {
    setLastTrip(trip)
    void analysis.run(trip)
  }

  /** Re-plan the same trip, leaving `offsetHours` after the departure that was analysed. */
  const leaveAt = (offsetHours: number) => {
    const option = data?.departure_plan.options[offsetHours]
    if (!lastTrip || !option) return
    const when = new Date(option.epoch * 1000)
    const trip = { ...lastTrip, departure: when.toISOString() }
    setLastTrip(trip)
    setSyncDeparture({ value: toLocalInputValue(when) })
    void analysis.run(trip)
  }

  const routes = useMemo(() => data?.routes ?? [], [data])

  return (
    <div className="app">
      <section className="map-pane" aria-label="Map">
        <MapView
          data={data}
          selectedId={selectedId}
          focusedCheckpoint={focusedCheckpoint}
          onSelectRoute={selectRoute}
          onFocusCheckpoint={setFocusedCheckpoint}
          heat={{ metric, hour, visible: showHeat }}
        />
        <div className="map-vignette" aria-hidden="true" />
        {data && (
          <ForecastPanel
            heatmap={data.heatmap}
            metric={metric}
            hour={targetHour}
            visible={showHeat}
            playing={playing}
            onMetric={setMetric}
            onHour={(h) => {
              setPlaying(false)
              setTargetHour(h)
            }}
            onVisible={(v) => {
              setShowHeat(v)
              if (!v) setPlaying(false)
            }}
            onPlaying={setPlaying}
          />
        )}
        {busy && (
          <div className="map-loading" role="status">
            <span className="radar" aria-hidden="true" />
            <span>
              <strong>Scanning routes</strong>
              Pulling forecasts for every checkpoint
            </span>
          </div>
        )}
      </section>

      <aside className="sidebar" aria-label="Trip planner and results">
        <header className="brand">
          <svg className="brand-mark" viewBox="0 0 40 40" width="38" height="38" aria-hidden="true">
            <path d="M20 2 36 8v13c0 9-6.5 15-16 17C10.5 36 4 30 4 21V8z" fill="#ffb81c" />
            <path d="M12 26c3-.5 4-9 8-9s5 7 8 6.5" fill="none" stroke="#0b0f14" strokeWidth="2.6" strokeLinecap="round" strokeDasharray="0.1 5.2" />
            <path d="M12 26c3-.5 4-9 8-9s5 7 8 6.5" fill="none" stroke="#0b0f14" strokeWidth="2.6" strokeLinecap="round" opacity="0.35" />
            <circle cx="12" cy="26" r="2.6" fill="#0b0f14" />
            <circle cx="28" cy="23.5" r="2.6" fill="#0b0f14" />
          </svg>
          <div>
            <h1>Clearway</h1>
            <p>Weather-aware truck routing</p>
          </div>
        </header>

        <div className="sidebar-scroll">
          <TripForm busy={busy} compact={status === 'success'} syncDeparture={syncDeparture} onSubmit={submit} />

          {error && (
            <div className="banner banner-error" role="alert">
              <strong>Couldn’t analyze this trip.</strong> {error}
            </div>
          )}

          {data && data.warnings.length > 0 && (
            <div className="banner banner-warn" role="status">
              {data.warnings.map((w) => (
                <p key={w}>{w}</p>
              ))}
            </div>
          )}

          {busy && !data && <Skeleton />}

          {routes.length > 0 && (
            <section className={`results${busy ? ' is-stale' : ''}`} aria-live="polite" aria-busy={busy}>
              {data && <DeparturePlanner plan={data.departure_plan} busy={busy} onLeaveAt={leaveAt} />}
              <h2 className="section-title">
                {routes.length} route{routes.length === 1 ? '' : 's'} <span>ranked for weather risk</span>
              </h2>
              {routes.map((route) => (
                <RouteCard
                  key={route.id}
                  route={route}
                  colorIndex={Number(route.id.slice(1)) - 1}
                  selected={route.id === selectedId}
                  focusedCheckpoint={route.id === selectedId ? focusedCheckpoint : null}
                  onSelect={() => selectRoute(route.id)}
                  onFocusCheckpoint={setFocusedCheckpoint}
                />
              ))}
              <p className="footnote">
                Ranking prefers the fewest Severe miles, then High miles, then lowest average risk, then the
                shortest time. Routes crossing No Travel conditions are always ranked last. Times are shown in each
                checkpoint’s local time zone.
              </p>
            </section>
          )}

          {status === 'idle' && !data && (
            <div className="empty-hint">
              <svg viewBox="0 0 220 70" aria-hidden="true">
                <path d="M6 54C40 54 52 14 88 14s44 40 80 36c20-2 36-14 46-30" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeDasharray="1 9" />
                <circle cx="6" cy="54" r="5" fill="#ffb81c" />
                <circle cx="214" cy="20" r="5" fill="#35d07f" />
              </svg>
              <p>
                Plan a trip to compare three routes. Each one is checked for wind, rain and snow at the time your
                truck will actually be there.
              </p>
            </div>
          )}

          <p className="credits">
            Routing © OpenStreetMap contributors via OSRM · Forecasts by Open-Meteo · Basemap © Esri
          </p>
        </div>
      </aside>
    </div>
  )
}

function Skeleton() {
  return (
    <div className="skeleton-list" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <div key={i} className="skeleton-card">
          <span /> <span /> <span />
        </div>
      ))}
    </div>
  )
}
