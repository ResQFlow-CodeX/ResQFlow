import { useCallback, useEffect, useRef, useState } from 'react'
import { LayoutDashboard, Building2, ClipboardList, HeartHandshake, BarChart3, Zap, RotateCcw, ShieldCheck } from 'lucide-react'
import { api } from './api'
import Overview from './pages/Overview'
import Campuses from './pages/Campuses'
import Requests from './pages/Requests'
import Donors from './pages/Donors'
import Reports from './pages/Reports'
import './styles.css'

const PAGES = [
  ['overview', 'Overview', LayoutDashboard, Overview],
  ['campuses', 'Campuses', Building2, Campuses],
  ['requests', 'Requests', ClipboardList, Requests],
  ['donors', 'Donors', HeartHandshake, Donors],
  ['reports', 'Reports', BarChart3, Reports],
]
const getPage = () => {
  const h = location.hash.slice(1)
  return PAGES.some((p) => p[0] === h) ? h : 'overview'
}
const EMPTY = {
  campuses: [], recs: [], transfers: [], requests: [], log: [], vehicles: [], donations: [],
  roads: { blocked_roads: [] }, impact: {}, forecast: { hours: [], series: [] },
}

export default function App() {
  const [page, setPage] = useState(getPage)
  const [data, setData] = useState(EMPTY)
  const [error, setError] = useState(null)
  const [toast, setToast] = useState(null)
  const [updated, setUpdated] = useState(null)
  const actionInFlight = useRef(false)
  const [disaster, setDisaster] = useState({ campus_id: 1, disaster_type: 'flood' })

  useEffect(() => {
    const onHash = () => setPage(getPage())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const refresh = useCallback(async () => {
    try {
      const [campuses, recs, transfers, requests, log, vehicles, donations, roads, impact, forecast] = await Promise.all([
        api.campuses(), api.recs(), api.transfers(), api.requests(), api.log(),
        api.vehicles(), api.donations(), api.roads(), api.impact(), api.forecast(),
      ])
      setData({ campuses, recs, transfers, requests, log, vehicles, donations, roads, impact, forecast })
      setUpdated(new Date())
      setError(null)
    } catch {
      setError('Cannot reach the backend. Start it with: uvicorn main:app --reload')
    }
  }, [])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 4000)
    return () => clearInterval(t)
  }, [refresh])

  const flash = (msg, bad = false) => {
    setToast({ msg, bad })
    setTimeout(() => setToast(null), 3500)
  }

  // Runs an API call, shows a message, then reloads everything.
  const act = async (fn, okMsg) => {
    if (actionInFlight.current) return undefined
    actionInFlight.current = true
    try {
      const out = await fn()
      if (okMsg) flash(okMsg)
      await refresh()
      return out
    } catch (e) {
      flash(e.message, true)
      return undefined
    } finally {
      actionInFlight.current = false
    }
  }

  const triggerDisaster = () => act(() => api.disaster({ campus_id: Number(disaster.campus_id), disaster_type: disaster.disaster_type }), ` ${disaster.disaster_type} simulated at ${data.campuses.find(c => c.id === Number(disaster.campus_id))?.name || 'selected campus'}`)

  const current = PAGES.find((p) => p[0] === page)
  const Page = current[3]

  return (
    <div className="app">
      <aside className="side">
        <div className="brand">
          <span className="logo">R</span>
          <div><b>ResQFlow</b><small>Smart response. Faster rescue.</small></div>
        </div>
        <nav>
          {PAGES.map(([id, label, Icon]) => (
            <a key={id} href={'#' + id} className={id === page ? 'on' : ''}>
              <Icon size={18} /> {label}
              {id === 'overview' && data.recs.length > 0 && <span className="dot-count">{data.recs.length}</span>}
            </a>
          ))}
        </nav>
        <p className="side-note"><ShieldCheck size={16} /> A coordinator approves every action.</p>
      </aside>

      <div className="content">
        <header className="topbar">
          <div>
            <h1>{current[1]}</h1>
            <span className="live"><i /> {updated ? `Updated ${updated.toLocaleTimeString()}` : 'Connecting'}</span>
          </div>
          <div className="demo-controls">
            <select aria-label="Affected campus" value={disaster.campus_id} onChange={e => setDisaster({ ...disaster, campus_id: Number(e.target.value) })}>
              {data.campuses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <select aria-label="Disaster type" value={disaster.disaster_type} onChange={e => setDisaster({ ...disaster, disaster_type: e.target.value })}>
              <option value="flood">Flood</option><option value="earthquake">Earthquake</option><option value="cyclone">Cyclone</option><option value="drought">Drought</option>
            </select>
            <button className="btn danger" onClick={triggerDisaster} disabled={!data.campuses.length}>
              <Zap size={16} /> Simulate disaster
            </button>
            <button className="btn" onClick={() => act(api.reset, 'Demo reset')}>
              <RotateCcw size={16} /> Reset demo
            </button>
          </div>
        </header>

        {error && <div className="banner">{error}</div>}
        {toast && <div className={'toast' + (toast.bad ? ' bad' : '')} role="status">{toast.msg}</div>}

        <main><Page data={data} act={act} /></main>
      </div>
    </div>
  )
}
