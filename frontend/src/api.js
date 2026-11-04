// All backend calls live here. Matches docs/API_CONTRACT.md.
async function req(path, opts = {}) {
  const res = await fetch('/api' + path, { headers: { 'Content-Type': 'application/json' }, ...opts })
  if (!res.ok) {
    let msg = res.statusText
    try {
      const d = (await res.json()).detail
      msg = typeof d === 'string' ? d : 'Please check the values you entered'
    } catch {}
    throw new Error(msg)
  }
  return res.json()
}
const post = (path, body) => req(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined })

export const api = {
  campuses: () => req('/campuses'),
  recs: () => req('/recommendations'),
  transfers: () => req('/transfers'),
  requests: () => req('/requests'),
  log: () => req('/log'),
  vehicles: () => req('/vehicles'),
  roads: () => req('/roads'),
  donations: () => req('/donations'),
  impact: () => req('/impact'),
  forecast: () => req('/forecast'),
  createTransfer: (body) => post('/transfers', body),
  advance: (id) => post(`/transfers/${id}/advance`),
  createRequest: (body) => post('/requests', body),
  donate: (body) => post('/donations', body),
  road: (body) => post('/roads', body),
  setVehicle: (id, available) => post(`/vehicles/${id}/availability`, { available }),
  updateStock: (body) => post('/inventory', body),
  consume: (body) => post('/inventory/consume', body),
  sms: (text) => post('/sms', { text }),
  disaster: (body) => post('/simulate/disaster', body),
  reset: () => post('/simulate/reset'),
}
