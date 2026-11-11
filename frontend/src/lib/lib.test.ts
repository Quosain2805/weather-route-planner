import { describe, expect, it } from 'vitest'
import { formatDelta, formatDuration, formatEta, toLocalInputValue, defaultDeparture } from './format'
import { colorAt, scalePosition, valueAt } from './heat'

const scales = { wind: [25, 35, 45, 55], rain: [0.1, 0.25, 0.5, 1], snow: [0.5, 1, 2, 3] }

describe('format', () => {
  it('formats durations', () => {
    expect(formatDuration(45 * 60)).toBe('45 min')
    expect(formatDuration(17 * 3600 + 48 * 60)).toBe('17 h 48 min')
    expect(formatDuration(3600)).toBe('1 h 00 min')
  })

  it('formats deltas against the fastest route', () => {
    expect(formatDelta(0)).toBe('Fastest')
    expect(formatDelta(75 * 60)).toBe('+1 h 15 min')
  })

  it('formats an ETA in the requested time zone', () => {
    const epoch = Date.UTC(2026, 10, 11, 21, 0) / 1000 // 21:00 UTC
    // Recent ICU versions put a narrow no-break space before "PM"; compare with plain spaces.
    expect(formatEta(epoch, 'America/Chicago').replace(/\s/g, ' ')).toMatch(/^Wed 3:00 PM CST$/)
  })

  it('survives an unknown time zone name', () => {
    expect(() => formatEta(0, 'Not/AZone')).not.toThrow()
  })

  it('builds a datetime-local value and a future default departure', () => {
    expect(toLocalInputValue(new Date(2026, 0, 5, 9, 7))).toBe('2026-01-05T09:07')
    const at = (h: number, m: number) => defaultDeparture(new Date(2026, 0, 5, h, m))
    expect(at(9, 40).getHours()).toBe(11) // 10:10 -> rounds up to 11:00
    expect(at(9, 30).getHours()).toBe(10) // exactly 10:00 is already 30 min away
    expect(at(9, 5).getHours()).toBe(10)
    expect(at(23, 50).getDate()).toBe(6) // rolls over midnight
    expect(at(9, 40).getMinutes()).toBe(0)
  })
})

describe('heat scale', () => {
  it('interpolates hourly values and clamps at the ends', () => {
    expect(valueAt([0, 10, 20], 0.5)).toBe(5)
    expect(valueAt([0, 10, 20], 1.25)).toBe(12.5)
    expect(valueAt([0, 10, 20], -3)).toBe(0)
    expect(valueAt([0, 10, 20], 99)).toBe(20)
  })

  it('places hazard values on the 0..4 scale using the server thresholds', () => {
    expect(scalePosition('wind', 0, scales)).toBe(0)
    expect(scalePosition('wind', 25, scales)).toBe(1)
    expect(scalePosition('wind', 35, scales)).toBe(2)
    expect(scalePosition('wind', 40, scales)).toBeCloseTo(2.5)
    expect(scalePosition('wind', 80, scales)).toBe(4)
    expect(scalePosition('rain', 0.5, scales)).toBe(3)
    expect(scalePosition('risk', 2.4, scales)).toBe(2.4)
  })

  it('blends colours between risk levels', () => {
    expect(colorAt(0)).toEqual([53, 208, 127])
    const mid = colorAt(0.5)
    expect(mid[0]).toBeGreaterThan(53)
    expect(mid[0]).toBeLessThan(255)
  })
})
