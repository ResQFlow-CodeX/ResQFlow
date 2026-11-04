import { useState } from 'react'
import { Download } from 'lucide-react'
import { fmtDateTime } from '../reports/dates'

const fmt = (v) => Number(v || 0).toLocaleString()

export default function Reports({ data }) {
  const { impact: i, log } = data
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  // The PDF library is loaded only when the button is clicked, so the rest of the app stays light.
  const download = async () => {
    setBusy(true)
    setError(null)
    try {
      const { downloadIncidentReport } = await import('../reports/incidentReport')
      downloadIncidentReport(data)
    } catch (e) {
      console.error(e)
      setError('Could not create the PDF. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <section className="impact">
        <div><b>{fmt(i.water_redirected_l)} L</b><span>water redirected</span></div>
        <div><b>{fmt(i.medicine_redirected_units)}</b><span>medicine units delivered</span></div>
        <div><b>{fmt(i.transfers_completed)}</b><span>transfers completed</span></div>
        <div><b>{fmt(i.donations_redirected)}</b><span>donations redirected</span></div>
      </section>

      <section className="block">
        <div className="row">
          <h3 className="h">Decision log</h3>
          <button className="btn" onClick={download} disabled={busy}>
            <Download size={16} />
            {busy ? 'Creating PDF...' : 'Download PDF Report'}
          </button>
        </div>
        {error && <p className="warn">{error}</p>}

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Action</th>
                <th>Transfer</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {log.length === 0 && (
                <tr><td colSpan="4" className="muted">No decisions yet.</td></tr>
              )}
              {log.map((e, k) => (
                <tr key={k}>
                  <td>{fmtDateTime(e.created_at)}</td>
                  <td>{e.action}</td>
                  <td>{e.summary}</td>
                  <td>{e.note || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}