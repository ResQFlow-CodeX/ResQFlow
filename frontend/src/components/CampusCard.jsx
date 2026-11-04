import { Droplets, Pill, CalendarClock } from 'lucide-react'

const ICON = { water: Droplets, medicine: Pill }
const fmt = (n) => Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })

export default function CampusCard({ campus }) {
  return (
    <article className="campus">
      <h3>{campus.name} {campus.disaster_type && <span className="chip warn">{campus.disaster_type}</span>}</h3>
      {campus.stocks.map((s) => {
        const Icon = ICON[s.resource] || Droplets
        const h = s.hours_to_empty
        const pct = Math.min(h, 48) / 48 * 100
        return (
          <div key={s.resource} className={'stock ' + s.status}>
            <div className="stock-head"><Icon size={16} /> <span>{s.resource}</span>
              {s.expiry_days !== null && s.expiry_days <= 14 && (
                <span className="chip warn"><CalendarClock size={12} /> expires in {s.expiry_days} d</span>
              )}
            </div>
            <div className="hours">{h >= 999 ? 'No use' : Math.round(h)}{h < 999 && <small> hours left</small>}</div>
            <div className="bar"><i style={{ width: pct + '%' }} /></div>
            <div className="stock-meta">
              <span>{fmt(s.quantity)} {s.unit} in stock</span>
              <span>Capacity {s.storage_capacity == null ? "—" : fmt(s.storage_capacity)} {s.storage_capacity == null ? "" : s.unit}</span>
            </div>
          </div>
        )
      })}
    </article>
  )
}
