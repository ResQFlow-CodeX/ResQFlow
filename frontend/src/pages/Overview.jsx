import CampusCard from '../components/CampusCard'
import Recommendations from '../components/Recommendations'
import Tracker from '../components/Tracker'
import MapView from '../components/MapView'
import ForecastChart from '../components/ForecastChart'
import Roads from '../components/Roads'

const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`

function situation(campuses, recs) {
  const low = campuses
    .flatMap((c) => c.stocks.map((s) => ({ campus: c.name, ...s })))
    .filter((s) => s.status !== 'green')
    .sort((a, b) => a.hours_to_empty - b.hours_to_empty)

  const waiting = recs.length
    ? `${plural(recs.length, 'recommended action')} waiting for your approval.`
    : 'No transfer can cover this yet. Check vehicles and roads.'

  if (low.length && low[0].status === 'red')
    return {
      tone: 'alert',
      title: `${low[0].campus} ${low[0].resource} will run out in about ${plural(Math.round(low[0].hours_to_empty), 'hour')}.`,
      sub: waiting,
      label: 'Critical situation',
    }

  if (low.length)
    return {
      tone: 'watch',
      title: `${low[0].campus} ${low[0].resource} is getting low, about ${plural(Math.round(low[0].hours_to_empty), 'hour')} left.`,
      sub: waiting,
      label: 'Attention required',
    }

  return {
    tone: 'calm',
    title: 'All campuses are covered.',
    sub: 'ResQFlow monitors stock and usage to flag shortages before they happen.',
    label: 'Systems operational',
  }
}

function Metric({ value, label }) {
  return (
    <div className="overview-metric">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  )
}

export default function Overview({ data, act }) {
  const { campuses, recs, transfers, requests, donations, impact, forecast, roads } = data

  const s = situation(campuses, recs)

  const atRisk = campuses.filter((c) =>
    c.stocks.some((x) => x.status !== 'green')
  ).length

  const inProgress = transfers.filter((t) =>
    ['approved', 'dispatched'].includes(t.status)
  ).length

  const totalWater = campuses.reduce(
    (n, c) => n + (c.stocks.find((x) => x.resource === 'water')?.quantity || 0),
    0
  )

  const totalCapacity = campuses.reduce(
    (n, c) => n + (c.stocks.find((x) => x.resource === 'water')?.storage_capacity || 0),
    0
  )

  const delivered =
    transfers
      .filter((t) => t.status === 'received')
      .reduce((n, t) => n + (t.resource === 'water' ? t.quantity : 0), 0) +
    donations
      .filter((d) => d.resource === 'water')
      .reduce((n, d) => n + d.quantity, 0)

  const critical = campuses.reduce(
    (n, c) => n + c.stocks.filter((x) => x.status === 'red').length,
    0
  )

  const surplus = campuses.filter((c) =>
    c.stocks.some(
      (x) =>
        x.resource === 'water' &&
        x.quantity > x.safety_reserve + x.consumption_rate * 24
    )
  ).length

  return (
    <div className="overview">
      <section className={`overview-hero ${s.tone}`}>
        <div>
          <span className="overview-status">
            <i />
            {s.label}
          </span>
          <h2>{s.title}</h2>
          <p>{s.sub}</p>
        </div>
      </section>

      <section className="overview-primary">
        <Metric value={atRisk} label="Campuses at risk" />
        <Metric value={requests.length} label="Open requests" />
        <Metric value={inProgress} label="Transfers in progress" />
        <Metric
          value={impact.donations_redirected ?? 0}
          label="Donations redirected"
        />
      </section>

      <section className="overview-section">
        <div className="overview-section-heading">
          <div>
            <h3>Resource overview</h3>
            <p>Current disaster response performance</p>
          </div>
        </div>

        <div className="overview-secondary">
          <Metric value={`${Math.round(totalWater).toLocaleString()} L`} label="Available water" />
          <Metric value={`${Math.round(totalCapacity).toLocaleString()} L`} label="Water capacity" />
          <Metric value={campuses.filter((c) => c.disaster_type).length} label="Affected campuses" />
          <Metric value={surplus} label="Campuses with surplus" />
          <Metric value={`${delivered.toLocaleString()} L`} label="Water delivered" />
          <Metric value={critical} label="Critical stock alerts" />
          <Metric value={impact.requests_fulfilled ?? 0} label="Requests fulfilled" />
        </div>
      </section>

      <section className="overview-section">
        <div className="overview-section-heading">
          <div>
            <h3>Campus status</h3>
            <p>Live resource availability across campuses</p>
          </div>
        </div>

        <div className="campus-row">
          {campuses.map((c) => (
            <CampusCard key={c.id} campus={c} />
          ))}
        </div>
      </section>

      <div className="grid-main overview-main-grid">
        <section className="block overview-panel">
          <h3 className="h">Live response map</h3>
          <MapView campuses={campuses} recs={recs} transfers={transfers} />
          <p className="muted small legend-note">
            Marker colour shows the lowest stock level at each campus.
            Dashed blue indicates a recommended route. Solid green indicates
            an approved or moving transfer.
          </p>
          <Roads campuses={campuses} roads={roads} act={act} />
        </section>

        <section className="block overview-panel">
          <h3 className="h">
            Recommended actions
            <span className="count">{recs.length}</span>
          </h3>
          <Recommendations recs={recs} act={act} />
        </section>
      </div>

      <div className="grid-2 overview-bottom-grid">
        <section className="block overview-panel">
          <h3 className="h">Stock forecast · Next 24 hours</h3>
          <ForecastChart forecast={forecast} />
        </section>

        <section className="block overview-panel">
          <h3 className="h">Transfer tracker</h3>
          <Tracker transfers={transfers} act={act} />
        </section>
      </div>
    </div>
  )
}