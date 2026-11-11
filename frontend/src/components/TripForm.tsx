import { useState } from 'react'
import type { FormEvent } from 'react'
import type { Place, TripRequest } from '../api/types'
import { defaultDeparture, formatLoad, formatSliderTime, toLocalInputValue } from '../lib/format'
import { PlaceInput } from './PlaceInput'

const INTERVALS = [10, 25, 50] as const
const MAX_LOAD_LB = 80_000
const MAX_DAYS_AHEAD = 7
const LOCAL_ZONE = Intl.DateTimeFormat().resolvedOptions().timeZone

const EXAMPLES: { name: string; origin: Place; destination: Place }[] = [
  {
    name: 'Chicago → Denver',
    origin: { label: 'Chicago, Illinois, United States', lat: 41.8781, lon: -87.6298 },
    destination: { label: 'Denver, Colorado, United States', lat: 39.7392, lon: -104.9903 },
  },
  {
    name: 'Salt Lake City → Denver',
    origin: { label: 'Salt Lake City, Utah, United States', lat: 40.7608, lon: -111.891 },
    destination: { label: 'Denver, Colorado, United States', lat: 39.7392, lon: -104.9903 },
  },
  {
    name: 'Dallas → Atlanta',
    origin: { label: 'Dallas, Texas, United States', lat: 32.7767, lon: -96.797 },
    destination: { label: 'Atlanta, Georgia, United States', lat: 33.749, lon: -84.388 },
  },
]

interface Props {
  busy: boolean
  /** True once results are showing: the form folds into a one-line summary with an Edit button. */
  compact: boolean
  /** Lets the app move the departure (for example "leave 4 h later"). A new object means a new value. */
  syncDeparture: { value: string } | null
  onSubmit: (trip: TripRequest) => void
}

type Errors = Partial<Record<'origin' | 'destination' | 'departure' | 'load', string>>

export function TripForm({ busy, compact, syncDeparture, onSubmit }: Props) {
  const [origin, setOrigin] = useState<Place | null>(null)
  const [destination, setDestination] = useState<Place | null>(null)
  const [departure, setDeparture] = useState(() => toLocalInputValue(defaultDeparture()))
  const [load, setLoad] = useState('38000')
  const [spacing, setSpacing] = useState<number>(25)
  const [errors, setErrors] = useState<Errors>({})
  const [editing, setEditing] = useState(true)
  const [seenSync, setSeenSync] = useState(syncDeparture)
  if (syncDeparture !== seenSync) {
    setSeenSync(syncDeparture)
    if (syncDeparture) setDeparture(syncDeparture.value)
  }
  const showSummary = compact && !editing

  const validate = (): Errors => {
    const next: Errors = {}
    if (!origin) next.origin = 'Pick a starting point from the suggestions.'
    if (!destination) next.destination = 'Pick a destination from the suggestions.'

    const when = new Date(departure)
    const now = Date.now()
    if (!departure || Number.isNaN(when.getTime())) next.departure = 'Choose a departure date and time.'
    else if (when.getTime() < now - 60 * 60 * 1000) next.departure = "Departure can't be in the past."
    else if (when.getTime() > now + MAX_DAYS_AHEAD * 24 * 3600 * 1000)
      next.departure = `Forecasts only reach about ${MAX_DAYS_AHEAD} days ahead.`

    const pounds = Number(load)
    if (load.trim() === '' || !Number.isFinite(pounds) || pounds < 0 || pounds > MAX_LOAD_LB)
      next.load = `Enter a load between 0 and ${MAX_LOAD_LB.toLocaleString('en-US')} lb.`
    return next
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const found = validate()
    setErrors(found)
    if (Object.keys(found).length > 0 || !origin || !destination) return
    setEditing(false)
    onSubmit({
      origin,
      destination,
      departure: new Date(departure).toISOString(),
      load_lb: Math.round(Number(load)),
      interval_miles: spacing,
    })
  }

  const swap = () => {
    setOrigin(destination)
    setDestination(origin)
  }

  return (
    <form className="trip-form" onSubmit={submit} noValidate>
      {showSummary && origin && destination && (
        <button type="button" className="trip-summary" onClick={() => setEditing(true)} aria-label="Edit trip">
          <span className="trip-summary-route">
            {origin.label.split(',')[0]} <i aria-hidden="true">→</i> {destination.label.split(',')[0]}
          </span>
          <span className="trip-summary-meta">
            {formatSliderTime(new Date(departure).getTime() / 1000)} · {formatLoad(Number(load))} · {spacing} mi
          </span>
          <span className="trip-summary-edit">Edit</span>
        </button>
      )}
      <div className={`form-fields${showSummary ? ' is-hidden' : ''}`}>
      <div className="places">
        <PlaceInput
          label="Origin"
          marker="A"
          placeholder="City or address"
          value={origin}
          onChange={setOrigin}
          error={errors.origin}
        />
        <button type="button" className="swap-btn" onClick={swap} aria-label="Swap origin and destination" title="Swap">
          ⇅
        </button>
        <PlaceInput
          label="Destination"
          marker="B"
          placeholder="City or address"
          value={destination}
          onChange={setDestination}
          error={errors.destination}
        />
      </div>

      <div className="row-2">
        <div className="field">
          <label htmlFor="departure" className="field-label">
            Departure
          </label>
          <input
            id="departure"
            type="datetime-local"
            value={departure}
            onChange={(e) => setDeparture(e.target.value)}
            aria-invalid={errors.departure ? true : undefined}
          />
          {errors.departure ? (
            <p className="field-error">{errors.departure}</p>
          ) : (
            <p className="field-hint">Your local time ({LOCAL_ZONE})</p>
          )}
        </div>
        <div className="field">
          <label htmlFor="load" className="field-label">
            Load weight
          </label>
          <div className="input-suffix">
            <input
              id="load"
              type="number"
              inputMode="numeric"
              min={0}
              max={MAX_LOAD_LB}
              step={500}
              value={load}
              onChange={(e) => setLoad(e.target.value)}
              aria-invalid={errors.load ? true : undefined}
            />
            <span aria-hidden="true">lb</span>
          </div>
          {errors.load && <p className="field-error">{errors.load}</p>}
        </div>
      </div>

      <fieldset className="field">
        <legend className="field-label">Check weather every</legend>
        <div className="segmented" role="radiogroup" aria-label="Weather checkpoint spacing">
          {INTERVALS.map((miles) => (
            <label key={miles} className={spacing === miles ? 'is-selected' : undefined}>
              <input
                type="radio"
                name="interval"
                value={miles}
                checked={spacing === miles}
                onChange={() => setSpacing(miles)}
              />
              {miles} mi
            </label>
          ))}
        </div>
      </fieldset>

      <button type="submit" className="primary-btn" disabled={busy}>
        {busy ? (
          <>
            <span className="spinner" aria-hidden="true" /> Analyzing routes…
          </>
        ) : (
          'Find safest route'
        )}
      </button>

      <div className="examples">
        <span>Try:</span>
        {EXAMPLES.map((ex) => (
          <button
            key={ex.name}
            type="button"
            className="chip"
            onClick={() => {
              setOrigin(ex.origin)
              setDestination(ex.destination)
              setErrors({})
            }}
          >
            {ex.name}
          </button>
        ))}
      </div>
      </div>
    </form>
  )
}
