import { useState } from 'react'

const COLORS = ['#4338ca', '#0891b2', '#9333ea', '#be185d']

export default function ForecastChart({ forecast }) {
  const [res, setRes] = useState('water')
  const hours = forecast.hours
  const series = forecast.series.filter((s) => s.resource === res)
  if (!hours.length || !series.length) return <p className="muted">Loading forecast.</p>

  const W = 640, H = 260, L = 56, R = 18, T = 16, B = 34
  const max = Math.max(1, ...series.flatMap((s) => s.values)) * 1.05
  const x = (h) => L + (h / (hours.length - 1)) * (W - L - R)
  const y = (v) => T + (1 - v / max) * (H - T - B)
  const unit = series[0].unit
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(max * f))

  return (
    <div className="forecast">
      <div className="tabs" role="tablist">
        {['water', 'medicine'].map((r) => (
          <button key={r} role="tab" aria-selected={r === res} className={r === res ? 'on' : ''} onClick={() => setRes(r)}>{r}</button>
        ))}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Projected ${res} stock over the next ${hours.length - 1} hours`}>
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} className="grid" />
            <text x={L - 8} y={y(t) + 4} textAnchor="end" className="axis">{t.toLocaleString()}</text>
          </g>
        ))}
        {[0, 6, 12, 18, 24].filter((h) => h < hours.length).map((h) => (
          <text key={h} x={x(h)} y={H - 10} textAnchor="middle" className="axis">{h === 0 ? 'Now' : `+${h} h`}</text>
        ))}
        <text x={14} y={T + 4} className="axis">{unit}</text>
        {series.map((s, i) => {
          const color = COLORS[i % COLORS.length]
          const pts = s.values.map((v, h) => `${x(h)},${y(v)}`).join(' ')
          return (
            <g key={s.campus}>
              <polyline points={pts} fill="none" stroke={color} strokeWidth="3" strokeLinejoin="round" />
              {s.runs_out_in !== null && (
                <g>
                  <circle cx={x(s.runs_out_in)} cy={y(0)} r="6" className="runout" />
                  <text x={x(s.runs_out_in) + 10} y={y(0) - 10} className="runout-label">{s.campus} runs out in {Math.round(s.runs_out_in)} h</text>
                </g>
              )}
            </g>
          )
        })}
      </svg>
      <ul className="legend-row">
        {series.map((s, i) => (
          <li key={s.campus}><i style={{ background: COLORS[i % COLORS.length] }} /> {s.campus}</li>
        ))}
      </ul>
    </div>
  )
}
