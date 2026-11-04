import { useState } from 'react'
import { api } from '../api'

const num = (v) => (v === '' ? '' : Number(v))

export default function Donors({ data, act }) {
  const { campuses, donations } = data
  const [don, setDon] = useState({ donor_name: 'Acme CSR', resource: 'water', quantity: 1000, intended_campus_id: 1 })
  const [result, setResult] = useState(null)
  const [donating, setDonating] = useState(false)
  const [transfer, setTransfer] = useState({ from_campus_id: campuses[0]?.id || 1, to_campus_id: campuses[1]?.id || 2, quantity: 100 })
  const [sending, setSending] = useState(false)

  const submit = async () => {
    if (donating || !don.donor_name.trim() || Number(don.quantity) <= 0) return
    setDonating(true)
    try {
      const out = await act(() => api.donate({ ...don, quantity: Number(don.quantity), intended_campus_id: Number(don.intended_campus_id) }))
      if (out) setResult(out)
    } finally { setDonating(false) }
  }

  const sendCampusTransfer = async () => {
    if (sending || !transfer.from_campus_id || !transfer.to_campus_id || transfer.from_campus_id === transfer.to_campus_id || Number(transfer.quantity) <= 0) return
    setSending(true)
    try {
      await act(() => api.createTransfer({
        from_campus_id: Number(transfer.from_campus_id), to_campus_id: Number(transfer.to_campus_id),
        resource: 'water', quantity: Number(transfer.quantity), action: 'approve',
        reasons: ['Manual coordinator-initiated campus transfer'],
      }), 'Campus transfer approved. Continue it from the Overview tracker.')
    } finally { setSending(false) }
  }

  return (
    <>
    <section className="block">
      <h3 className="h">Campus-to-campus water transfer</h3>
      <p className="muted small">Approve a direct transfer between campuses. Stock is deducted at dispatch and credited at receipt; the tracker shows the ETA.</p>
      <div className="form">
        <label>Donor campus<select value={transfer.from_campus_id} onChange={e => setTransfer({ ...transfer, from_campus_id: Number(e.target.value) })}>
          {campuses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select></label>
        <label>Receiving campus<select value={transfer.to_campus_id} onChange={e => setTransfer({ ...transfer, to_campus_id: Number(e.target.value) })}>
          {campuses.filter(c => c.id !== transfer.from_campus_id).map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select></label>
        <label>Quantity (litres)<input type="number" min="1" value={transfer.quantity} onChange={e => setTransfer({ ...transfer, quantity: e.target.value })} /></label>
        <button className="btn primary" disabled={sending || Number(transfer.quantity) <= 0 || transfer.from_campus_id === transfer.to_campus_id} onClick={sendCampusTransfer}>{sending ? 'Approving…' : 'Approve transfer'}</button>
      </div>
    </section>
    <div className="grid-2">
      <section className="block">
        <h3 className="h">Offer a donation</h3>
        <p className="muted small">ResQFlow checks where the donation is still needed, so it does not pile up where need is already covered.</p>
        <div className="form">
          <label>Donor name<input value={don.donor_name} onChange={(e) => setDon({ ...don, donor_name: e.target.value })} /></label>
          <label>Resource
            <select value={don.resource} onChange={(e) => setDon({ ...don, resource: e.target.value })}><option>water</option><option>medicine</option></select>
          </label>
          <label>Quantity<input type="number" min="1" value={don.quantity} onChange={(e) => setDon({ ...don, quantity: num(e.target.value) })} /></label>
          <label>Donor wants to help
            <select value={don.intended_campus_id} onChange={(e) => setDon({ ...don, intended_campus_id: e.target.value })}>
              {campuses.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <button className="btn primary wide" disabled={donating || !don.donor_name.trim() || Number(don.quantity) <= 0} onClick={submit}>{donating ? "Processing…" : "Offer donation"}</button>
        </div>
        {result && (
          <div className={'result ' + (result.accepted_as_intended ? 'ok' : 'redirect')}>
            <b>{result.accepted_as_intended ? 'Accepted as intended' : `Redirected to ${result.redirected_campus ? result.redirected_campus.name : 'no campus'}`}</b>
            <p>{result.message}</p>
          </div>
        )}
      </section>

      <section className="block">
        <h3 className="h">Donation history <span className="count">{donations.length}</span></h3>
        {donations.length === 0 && <p className="muted">No donations yet.</p>}
        <ul className="plain-list">
          {donations.map((d) => (
            <li key={d.id}>
              <b>{d.donor_name}</b> gave {d.quantity.toLocaleString()} of {d.resource}
              {d.redirected
                ? <span className="chip warn">Redirected from {d.intended_campus} to {d.redirected_campus}</span>
                : <span className="chip ok">To {d.redirected_campus || d.intended_campus}</span>}
            </li>
          ))}
        </ul>
      </section>
    </div>
    </>
  )
}
