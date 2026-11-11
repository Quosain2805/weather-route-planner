import { useId, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import type { Place } from '../api/types'
import { usePlaceSearch } from '../hooks/usePlaceSearch'

interface Props {
  label: string
  marker: string
  placeholder: string
  value: Place | null
  onChange: (place: Place | null) => void
  error?: string
}

export function PlaceInput({ label, marker, placeholder, value, onChange, error }: Props) {
  const id = useId()
  const listId = `${id}-list`
  const [text, setText] = useState(value?.label ?? '')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)

  // Keep the box in step when the parent sets a place (example trips, swap).
  const [seenValue, setSeenValue] = useState(value)
  if (value !== seenValue) {
    setSeenValue(value)
    if (value) setText(value.label)
  }

  const { results, loading, failed } = usePlaceSearch(text, value === null)
  const showList = open && value === null && text.trim().length >= 3
  const optionId = (i: number) => `${id}-opt-${i}`

  const choose = (place: Place) => {
    setText(place.label)
    setOpen(false)
    setActive(-1)
    onChange(place)
  }

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (!showList) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((i) => Math.min(results.length - 1, i + 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((i) => Math.max(0, i - 1))
    } else if (e.key === 'Enter' && results.length > 0) {
      e.preventDefault()
      choose(results[active >= 0 ? active : 0])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  const status = loading ? 'Searching…' : failed ? 'Search is unavailable right now' : 'No places found'

  return (
    <div className="field">
      <label htmlFor={id} className="field-label">
        {label}
      </label>
      <div className={`place-box${error ? ' has-error' : ''}`}>
        <span className="place-marker" aria-hidden="true">
          {marker}
        </span>
        <input
          ref={inputRef}
          id={id}
          type="text"
          role="combobox"
          autoComplete="off"
          spellCheck={false}
          placeholder={placeholder}
          value={text}
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={active >= 0 ? optionId(active) : undefined}
          aria-invalid={error ? true : undefined}
          onChange={(e) => {
            setText(e.target.value)
            setOpen(true)
            setActive(-1)
            if (value) onChange(null) // editing invalidates the previous choice
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
        />
        {text && (
          <button
            type="button"
            className="icon-btn"
            aria-label={`Clear ${label.toLowerCase()}`}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => {
              setText('')
              onChange(null)
              inputRef.current?.focus()
            }}
          >
            ×
          </button>
        )}
        {showList && (
          <ul id={listId} role="listbox" className="suggestions">
            {results.length === 0 ? (
              <li className="suggestion-status" role="presentation">
                {status}
              </li>
            ) : (
              results.map((place, i) => (
                <li
                  key={`${place.lat},${place.lon},${i}`}
                  id={optionId(i)}
                  role="option"
                  aria-selected={i === active}
                  className={i === active ? 'is-active' : undefined}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => choose(place)}
                  onMouseEnter={() => setActive(i)}
                >
                  {place.label}
                </li>
              ))
            )}
          </ul>
        )}
      </div>
      {error && <p className="field-error">{error}</p>}
    </div>
  )
}
