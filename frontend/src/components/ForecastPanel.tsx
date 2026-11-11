import type { Heatmap } from '../api/types'
import { formatSliderTime } from '../lib/format'
import { legendGradient, legendTicks, METRIC_LABELS, metricUnit } from '../lib/heat'
import type { HeatMetric } from '../lib/heat'

interface Props {
  heatmap: Heatmap
  metric: HeatMetric
  hour: number
  visible: boolean
  playing: boolean
  onMetric: (m: HeatMetric) => void
  onHour: (h: number) => void
  onVisible: (v: boolean) => void
  onPlaying: (p: boolean) => void
}

const METRICS: HeatMetric[] = ['risk', 'wind', 'rain', 'snow']

export function ForecastPanel({ heatmap, metric, hour, visible, playing, onMetric, onHour, onVisible, onPlaying }: Props) {
  const when = heatmap.start_epoch + hour * 3600
  const ticks = legendTicks(metric, heatmap.scales)
  const unit = metricUnit(metric)

  return (
    <section className="forecast-panel" aria-label="Weather heatmap controls">
      <div className="fp-row">
        <div className="fp-time">
          <span className="fp-label">Forecast</span>
          <strong>{formatSliderTime(when)}</strong>
          <span className="fp-offset">{hour === 0 ? 'departure' : `+${hour} h`}</span>
        </div>
        <div className="segmented segmented-sm" role="radiogroup" aria-label="Heatmap layer">
          {METRICS.map((m) => (
            <label key={m} className={visible && metric === m ? 'is-selected' : undefined}>
              <input
                type="radio"
                name="metric"
                checked={visible && metric === m}
                onChange={() => {
                  onMetric(m)
                  onVisible(true)
                }}
              />
              {METRIC_LABELS[m]}
            </label>
          ))}
          <label className={!visible ? 'is-selected' : undefined}>
            <input type="radio" name="metric" checked={!visible} onChange={() => onVisible(false)} />
            Off
          </label>
        </div>
      </div>

      <div className="fp-slider">
        <button
          type="button"
          className="play-btn"
          onClick={() => onPlaying(!playing)}
          aria-label={playing ? 'Pause forecast animation' : 'Play forecast animation'}
          disabled={!visible}
        >
          {playing ? '❚❚' : '▶'}
        </button>
        <div className="slider-wrap">
          <input
            type="range"
            min={0}
            max={heatmap.hours}
            step={1}
            value={hour}
            onChange={(e) => onHour(Number(e.target.value))}
            aria-label="Hours after departure"
            aria-valuetext={`${hour} hours after departure, ${formatSliderTime(when)}`}
            disabled={!visible}
            style={{ '--fill': `${(hour / heatmap.hours) * 100}%` } as React.CSSProperties}
          />
          <div className="slider-ticks" aria-hidden="true">
            {[0, 12, 24, 36, 48].map((h) => (
              <span key={h}>{h === 0 ? 'Departure' : `+${h} h`}</span>
            ))}
          </div>
        </div>
      </div>

      <div className="legend">
        <div className="legend-bar" style={{ background: legendGradient() }} />
        <div className="legend-ticks">
          {ticks.map((t) => (
            <span key={t}>{t}</span>
          ))}
        </div>
        {unit && <span className="legend-unit">{unit}</span>}
      </div>
    </section>
  )
}
