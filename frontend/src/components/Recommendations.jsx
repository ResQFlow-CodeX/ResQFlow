import { useState } from 'react'
import { ArrowRight, Check, Pencil, X, CircleCheck } from 'lucide-react'
import { api } from '../api'

const fmt = (n) => Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })

function RecCard({ rec, act }) {
  const [editing, setEditing] = useState(false)
  const [qty, setQty] = useState(rec.quantity)

  const base = {
    from_campus_id: rec.from_campus.id, to_campus_id: rec.to_campus.id,
    resource: rec.resource, reasons: rec.reasons,
  }
  const send = (action, quantity, note, msg) =>
    act(() => api.createTransfer({ ...base, quantity, action, note }), msg)

  return (
    <article className={'rec' + (rec.feasible ? '' : ' infeasible')}>
      <div className="rec-top">
        <h4>Send {fmt(rec.quantity)} {rec.unit} of {rec.resource}</h4>
        <span className="score" title="Priority score: 60% time left, 40% how critical the supply is">Priority {rec.priority_score}</span>
      </div>
      <p className="route">
        {rec.from_campus.name} <ArrowRight size={15} /> {rec.to_campus.name}
        <span className="muted"> {rec.distance_km} km, about {rec.eta_minutes} min{rec.vehicle ? ` by ${rec.vehicle}` : ''} · {rec.route_source === 'osrm' ? 'OSRM' : 'offline estimate'}</span>
      </p>
      <p className="why">Why this transfer</p>
      <ul className="reasons">
        {rec.reasons.map((r, i) => <li key={i}><CircleCheck size={15} /> <span>{r}</span></li>)}
      </ul>
      {!rec.feasible && <p className="warn">Not feasible right now. Fix the issue above or decline.</p>}

      {editing ? (
        <div className="actions">
          <input type="number" min="1" value={qty} onChange={(e) => setQty(e.target.value)} aria-label="Quantity to send" />
          <span className="muted small">{rec.unit}. Recommended: {fmt(rec.quantity)}</span>
          <button className="btn primary" onClick={() =>
            send('modify', Number(qty), `Quantity changed from ${rec.quantity} to ${qty}`, 'Modified and approved')}>
            Approve changed amount
          </button>
          <button className="btn plain" onClick={() => setEditing(false)}>Cancel</button>
        </div>
      ) : (
        <div className="actions">
          <button className="btn primary" disabled={!rec.feasible}
            onClick={() => send('approve', rec.quantity, null, 'Transfer approved')}><Check size={16} /> Approve</button>
          <button className="btn" disabled={!rec.feasible} onClick={() => setEditing(true)}><Pencil size={15} /> Modify</button>
          <button className="btn plain"
            onClick={() => send('decline', rec.quantity, 'Declined by coordinator', 'Transfer declined')}><X size={16} /> Decline</button>
        </div>
      )}
    </article>
  )
}

export default function Recommendations({ recs, act }) {
  if (recs.length === 0)
    return <p className="empty"><CircleCheck size={18} /> Every need is covered. No transfers to approve.</p>
  return <div className="recs">{recs.map((r) => <RecCard key={r.key + r.quantity} rec={r} act={act} />)}</div>
}
