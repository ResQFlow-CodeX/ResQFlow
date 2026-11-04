import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const COLORS = { green: '#1f9d55', amber: '#d98a00', red: '#d33a3a' }
const RANK = { green: 0, amber: 1, red: 2 }
const fmt = (n) => Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })

export default function MapView({ campuses, recs, transfers }) {
  const el = useRef(null)
  const map = useRef(null)
  const layer = useRef(null)
  const fitted = useRef(false)

  // Create the map once.
  useEffect(() => {
    map.current = L.map(el.current).setView([12.94, 77.67], 11)
    // Map tiles need internet. Without it the map stays grey, but markers and routes still draw.
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18, attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map.current)
    layer.current = L.layerGroup().addTo(map.current)
    return () => { map.current.remove(); map.current = null }
  }, [])

  // Redraw markers and routes whenever data changes.
  useEffect(() => {
    const g = layer.current
    if (!g) return
    g.clearLayers()

    // Approved / in-transit transfers: solid green
    transfers.filter((t) => t.route && t.route.length > 1).forEach((t) => {
      L.polyline(t.route, { color: '#1f9d55', weight: 5, opacity: 0.85 })
        .bindTooltip(`${fmt(t.quantity)} ${t.unit} ${t.resource} (${t.status})`, { sticky: true })
        .addTo(g)
    })

    // Recommended routes: dashed blue
    recs.forEach((r) => {
      L.polyline(r.route, { color: '#3b4cca', weight: 4, dashArray: '10 8' })
        .bindTooltip(`${fmt(r.quantity)} ${r.unit} ${r.resource} · ${r.distance_km} km · ${r.eta_minutes} min`, { sticky: true })
        .addTo(g)
    })

    // Campus markers, coloured by their worst stock
    campuses.forEach((c) => {
      const worst = c.stocks.reduce((w, s) => (RANK[s.status] > RANK[w] ? s.status : w), 'green')
      const low = [...c.stocks].sort((a, b) => a.hours_to_empty - b.hours_to_empty)[0]
      const hours = low && low.hours_to_empty < 999 ? `${low.resource}: ${low.hours_to_empty} h` : ''
      L.circleMarker([c.lat, c.lng], { radius: 11, color: '#fff', weight: 3, fillColor: COLORS[worst], fillOpacity: 1 })
        .bindTooltip(`<b>${c.name}</b><br>${hours}`, { permanent: true, direction: 'top', offset: [0, -10], className: 'campus-label' })
        .addTo(g)
    })

    if (!fitted.current && campuses.length) {
      map.current.fitBounds(campuses.map((c) => [c.lat, c.lng]), { padding: [60, 60] })
      fitted.current = true
    }
  }, [campuses, recs, transfers])

  return <div ref={el} className="map" />
}
