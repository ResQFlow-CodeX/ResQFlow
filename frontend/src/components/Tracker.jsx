import { api } from '../api'

const STEPS = ['approved', 'dispatched', 'received']
const NEXT = { approved: 'Mark dispatched', dispatched: 'Mark received' }
const fmt = (n) => Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })

export default function Tracker({ transfers, act }) {
  if (transfers.length === 0) return <p className="muted">No transfers yet. Approved transfers appear here.</p>
  return (
    <div className="tracker">
      {transfers.map((t) => (
        <article key={t.id} className="transfer">
          <div className="row">
            <b>Transfer #{t.id} · {fmt(t.quantity)} {t.unit} {t.resource}</b>
            <span className="muted">{t.from_campus} to {t.to_campus}</span>
            {t.status === 'declined' && <span className="chip bad">Declined</span>}
          </div>
          <p className="muted small">{t.distance_km ?? '—'} km · ETA {t.eta_minutes ?? '—'} min · {t.route_source === 'estimate' ? 'offline estimate' : t.route_source === 'osrm' ? 'OSRM road route' : 'route pending'}</p>
          {t.estimated_arrival_at && <p className="muted small">Estimated arrival: {new Date(t.estimated_arrival_at).toLocaleString()}</p>}
          {t.dispatched_at && <p className="muted small">Dispatched: {new Date(t.dispatched_at).toLocaleString()}</p>}
          {t.received_at && <p className="muted small">Received: {new Date(t.received_at).toLocaleString()}</p>}
          {t.status !== 'declined' && (
            <ol className="steps">
              {STEPS.map((s, i) => (
                <li key={s} className={i <= STEPS.indexOf(t.status) ? 'done' : ''}>{s}</li>
              ))}
            </ol>
          )}
          {NEXT[t.status] && (
            <button className="btn small" onClick={() => act(() => api.advance(t.id), t.status === 'approved' ? 'Transfer dispatched' : 'Transfer received')}>
              {NEXT[t.status]}
            </button>
          )}
        </article>
      ))}
    </div>
  )
}
