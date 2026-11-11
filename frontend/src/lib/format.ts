export function formatDuration(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60)
  const h = Math.floor(totalMinutes / 60)
  const m = totalMinutes % 60
  if (h === 0) return `${m} min`
  return `${h} h ${String(m).padStart(2, '0')} min`
}

export function formatMiles(miles: number): string {
  return `${Math.round(miles).toLocaleString('en-US')} mi`
}

/** Signed difference to the fastest route, e.g. "+1 h 12 min" or "Fastest". */
export function formatDelta(seconds: number): string {
  if (Math.abs(seconds) < 60) return 'Fastest'
  return `${seconds > 0 ? '+' : '−'}${formatDuration(Math.abs(seconds))}`
}

function dateTimeFormat(options: Intl.DateTimeFormatOptions, timeZone?: string) {
  try {
    return new Intl.DateTimeFormat('en-US', { ...options, timeZone })
  } catch {
    return new Intl.DateTimeFormat('en-US', options) // unknown zone name: fall back to the browser's
  }
}

/** "Tue 3:40 PM CST" in the given IANA zone (or the browser's when omitted). */
export function formatEta(epochSeconds: number, timeZone?: string): string {
  const parts = dateTimeFormat(
    { weekday: 'short', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' },
    timeZone,
  ).formatToParts(epochSeconds * 1000)
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? ''
  const time = `${get('hour')}:${get('minute')} ${get('dayPeriod')}`.trim()
  return `${get('weekday')} ${time} ${get('timeZoneName')}`.trim()
}

/** "Tue, Nov 11 · 3:00 PM" in the browser's zone. */
export function formatSliderTime(epochSeconds: number): string {
  const d = new Date(epochSeconds * 1000)
  const day = dateTimeFormat({ weekday: 'short', month: 'short', day: 'numeric' }).format(d)
  const time = dateTimeFormat({ hour: 'numeric', minute: '2-digit' }).format(d)
  return `${day} · ${time}`
}

export function formatLoad(pounds: number): string {
  return `${pounds.toLocaleString('en-US')} lb`
}

/** Value for <input type="datetime-local">, in the browser's local time. */
export function toLocalInputValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}

/** The next top-of-the-hour that is at least 30 minutes away: a sensible default departure. */
export function defaultDeparture(now = new Date()): Date {
  const d = new Date(now.getTime() + 30 * 60 * 1000)
  if (d.getMinutes() > 0 || d.getSeconds() > 0 || d.getMilliseconds() > 0) {
    d.setHours(d.getHours() + 1, 0, 0, 0)
  }
  return d
}
