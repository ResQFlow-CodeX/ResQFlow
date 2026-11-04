// The backend sends UTC timestamps without a "Z" (e.g. 2026-11-04T09:03:33).
// new Date() would read those as LOCAL time and show the wrong hour, so add the Z first.
export function parseUtc(value) {
  if (!value) return null
  const s = String(value)
  const hasZone = /[zZ]$|[+-]\d\d:?\d\d$/.test(s)
  const d = new Date(hasZone ? s : s + 'Z')
  return Number.isNaN(d.getTime()) ? null : d
}

export const fmtTime = (value) => {
  const d = parseUtc(value)
  return d ? d.toLocaleTimeString('en-GB') : 'N/A'
}

export const fmtDateTime = (value) => {
  const d = parseUtc(value)
  return d ? d.toLocaleString('en-GB') : 'N/A'
}