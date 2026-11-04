import { useState } from 'react'
import { api } from '../api'

const num = (v) => (v === '' ? '' : Number(v))

export default function Requests({ data, act }) {
  const { campuses, requests } = data
  const [req, setReq] = useState({ campus_id: 3, resource: 'medicine', quantity: 30, deadline_hours: 4 })

  return (
    <div className="grid-2">
      <section className="block">
        <h3 className="h">Raise a request</h3>
        <div className="form">
          <label>Campus
            <select value={req.campus_id} onChange={(e) => setReq({ ...req, campus_id: Number(e.target.value) })}>
              {campuses.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label>Resource
            <select value={req.resource} onChange={(e) => setReq({ ...req, resource: e.target.value })}><option>medicine</option><option>water</option></select>
          </label>
          <label>Quantity needed<input type="number" min="1" value={req.quantity} onChange={(e) => setReq({ ...req, quantity: num(e.target.value) })} /></label>
          <label>Needed within (hours)<input type="number" min="1" value={req.deadline_hours} onChange={(e) => setReq({ ...req, deadline_hours: num(e.target.value) })} /></label>
          <button className="btn primary wide" onClick={() => act(() => api.createRequest(req), 'Request raised. Check Overview for the recommendation.')}>Raise request</button>
        </div>
      </section>

      <section className="block">
        <h3 className="h">Open requests <span className="count">{requests.length}</span></h3>
        {requests.length === 0 && <p className="muted">No open requests. Raised requests appear here until a transfer is received.</p>}
        <ul className="plain-list">
          {requests.map((r) => (
            <li key={r.id}>
              <b>{r.campus}</b> needs {r.quantity.toLocaleString()} {r.unit} of {r.resource}
              <span className="chip warn">within {r.deadline_hours} h</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
