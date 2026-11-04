import { jsPDF } from 'jspdf'
import autoTable from 'jspdf-autotable'
import { fmtTime } from './dates.js'

/* ---------- design tokens (matched to the reference report) ---------- */
const C = {
  navy: [17, 24, 39], blue: [37, 99, 235], red: [220, 38, 38], green: [5, 150, 105], amber: [217, 119, 6],
  slate: [100, 116, 139], light: [241, 245, 249], text: [17, 24, 39], pale: [203, 213, 225],
  white: [255, 255, 255], line: [226, 232, 240],
}
const PAGE_W = 595.28
const PAGE_H = 841.89
const M = 42                       // left / right margin
const CW = PAGE_W - 2 * M          // content width
const TOP = 46                     // content start on pages after the first
const FOOT_LINE = 800              // page footer line
const BOTTOM = 788                 // content must end above the footer

/* ---------- small helpers ---------- */
const n0 = (v) => Number(v || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })
const qty = (v, unit) => `${n0(v)} ${unit || ''}`.trim()
const cap = (s) => (s ? String(s).charAt(0).toUpperCase() + String(s).slice(1) : 'N/A')
const stamp = (d = new Date()) => d.toLocaleString('en-GB')

function ensureSpace(doc, y, height) {
  if (y + height > BOTTOM) {
    doc.addPage()
    return TOP
  }
  return y
}

// Dark rounded section header. Returns the y just below the bar.
function sectionBar(doc, y, title) {
  doc.setFillColor(...C.navy)
  doc.roundedRect(M, y, CW, 28, 5, 5, 'F')
  doc.setTextColor(...C.white)
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(9.5)
  doc.text(title, M + 12, y + 18, { charSpace: 0.2 })
  return y + 28
}

// Label / value rows with no borders (Incident Information, Response Status).
function infoRows(doc, y, rows) {
  const ROW = 20
  rows.forEach(([label, value], i) => {
    const base = y + 17 + i * ROW
    doc.setFont('helvetica', 'bold').setFontSize(8).setTextColor(...C.slate)
    doc.text(label, M + 6, base)
    doc.setFont('helvetica', 'normal').setFontSize(8).setTextColor(...C.text)
    doc.text(String(value), M + 156, base, { maxWidth: CW - 160 })
  })
  return y + 8 + rows.length * ROW
}

// Rounded stat cards, three per row.
function statCards(doc, y, cards) {
  const GAP = 11
  const w = (CW - 2 * GAP) / 3
  const h = 63
  cards.forEach((card, i) => {
    const col = i % 3
    const row = Math.floor(i / 3)
    const x = M + col * (w + GAP)
    const top = y + row * (h + GAP)
    doc.setFillColor(...C.light)
    doc.roundedRect(x, top, w, h, 6, 6, 'F')
    doc.setFont('helvetica', 'normal').setFontSize(7).setTextColor(...C.slate)
    doc.text(card.label, x + 10, top + 21, { charSpace: 0.2 })
    doc.setFont('helvetica', 'bold').setFontSize(18).setTextColor(...card.color)
    doc.text(String(card.value), x + 10, top + 47)
  })
  const rows = Math.ceil(cards.length / 3)
  return y + rows * h + (rows - 1) * GAP
}

// Blue-header table with light zebra rows. Returns the y below the table.
function dataTable(doc, y, head, body, widths, { colorCol, colors } = {}) {
  const rows = body.length
    ? body
    : [[{ content: 'No records.', colSpan: head.length, styles: { textColor: C.slate, fontStyle: 'italic' } }]]
  autoTable(doc, {
    startY: y,
    head: [head],
    body: rows,
    theme: 'plain',
    margin: { left: M, right: M, top: TOP, bottom: PAGE_H - BOTTOM },
    styles: {
      font: 'helvetica', fontSize: 7.5, textColor: C.text, valign: 'middle', overflow: 'linebreak',
      cellPadding: { top: 8, bottom: 8, left: 8, right: 6 },
    },
    headStyles: { fillColor: C.blue, textColor: C.white, fontStyle: 'bold', fontSize: 7.5, cellPadding: { top: 9.5, bottom: 9.5, left: 8, right: 6 } },
    columnStyles: Object.fromEntries(widths.map((w, i) => [i, { cellWidth: w }])),
    rowPageBreak: 'avoid',
    didParseCell: (d) => {
      if (d.section !== 'body') return
      if (d.row.index % 2 === 0) d.cell.styles.fillColor = C.light
      if (colorCol !== undefined && d.column.index === colorCol && colors) {
        const hit = colors[String(d.cell.raw).toLowerCase()]
        if (hit) { d.cell.styles.textColor = hit; d.cell.styles.fontStyle = 'bold' }
      }
    },
  })
  return doc.lastAutoTable.finalY
}

// Space a table needs before we start it: short tables (8 rows or fewer) stay together on one page;
// long ones only need the header plus 3 rows so they can flow across pages.
const tableMin = (rows) => 40 + 26 * (rows <= 8 ? Math.max(rows, 1) : 3)

// Keeps a section bar from being stranded at the bottom of a page.
function startSection(doc, y, title, minBelow = 96) {
  y = ensureSpace(doc, y, 28 + minBelow)
  return sectionBar(doc, y, title)
}

/* ---------- the report ---------- */
export function buildIncidentReport(data = {}) {
  const {
    campuses = [], transfers = [], vehicles = [], requests = [], donations = [], log = [],
    roads = { blocked_roads: [] }, impact = {},
  } = data

  const now = new Date()
  const generated = stamp(now)
  const incidentId = `incident-${now.getTime()}-${Math.random().toString(36).slice(2, 7)}`

  /* derive the situation from live data */
  const stocks = campuses.flatMap((c) => c.stocks.map((s) => ({ campus: c.name, ...s })))
  const red = stocks.filter((s) => s.status === 'red')
  const amber = stocks.filter((s) => s.status === 'amber')
  const atRisk = [...red, ...amber].sort((a, b) => a.hours_to_empty - b.hours_to_empty)
  const inTransit = transfers.filter((t) => ['approved', 'dispatched'].includes(t.status))
  const dispatched = transfers.filter((t) => t.status !== 'declined')
  const names = Object.fromEntries(campuses.map((c) => [c.id, c.name]))
  const blocked = (roads.blocked_roads || []).map(([a, b]) => `${names[a] || a} - ${names[b] || b}`)

  let status = { word: 'STABLE', color: C.green }
  if (red.length) status = { word: 'ACTIVE', color: C.red }
  else if (amber.length || inTransit.length) status = { word: 'MONITORING', color: C.amber }
  const latest = transfers[0] ? transfers[0].status : null

  const doc = new jsPDF({ unit: 'pt', format: 'a4', orientation: 'portrait' })
  doc.setProperties({ title: 'ResQFlow Incident Report', subject: incidentId, author: 'ResQFlow' })

  /* ===== page 1 header band ===== */
  doc.setFillColor(...C.navy)
  doc.rect(0, 0, PAGE_W, 128, 'F')
  doc.setFillColor(...C.blue)
  doc.rect(0, 0, 8, 128, 'F')
  doc.setTextColor(...C.white).setFont('helvetica', 'bold').setFontSize(25)
  doc.text('ResQFlow', M, 58)
  doc.setFont('helvetica', 'normal').setFontSize(8).setTextColor(...C.pale)
  doc.text(generated, PAGE_W - M, 55, { align: 'right' })
  doc.setFontSize(8.6)
  doc.text('EMERGENCY OPERATIONS & INCIDENT REPORT', M, 82, { charSpace: 0.25 })
  doc.text('SMART RESPONSE. SAFER LIVES.', M, 101, { charSpace: 0.25 })

  /* title */
  doc.setTextColor(...C.text).setFont('helvetica', 'bold').setFontSize(18)
  doc.text('Incident Situation Report', M, 160)
  doc.setFont('helvetica', 'normal').setFontSize(9).setTextColor(...C.slate)
  doc.text(`Incident Reference: ${incidentId}`, M, 182)

  /* status banner */
  let y = 219
  doc.setFillColor(...status.color)
  doc.roundedRect(M, y, CW, 47, 6, 6, 'F')
  doc.setTextColor(...C.white).setFont('helvetica', 'bold').setFontSize(12)
  doc.text(`INCIDENT STATUS: ${status.word}`, M + 14, y + 20)
  doc.setFontSize(8.5)
  doc.text(`TRANSFER: ${latest ? latest.toUpperCase() : 'NONE'}`, M + 14, y + 35)
  y += 47 + 18

  /* operational summary */
  y = sectionBar(doc, y, 'OPERATIONAL SUMMARY') + 10
  y = statCards(doc, y, [
    { label: 'DISPATCHES', value: n0(dispatched.length), color: C.blue },
    { label: 'TRANSFERS IN TRANSIT', value: n0(inTransit.length), color: C.green },
    { label: 'TRANSFERS COMPLETED', value: n0(impact.transfers_completed), color: C.text },
    { label: 'WATER MOVED', value: qty(impact.water_redirected_l, 'L'), color: C.blue },
    { label: 'MEDICINE MOVED', value: n0(impact.medicine_redirected_units), color: C.green },
    { label: 'DONATIONS REDIRECTED', value: n0(impact.donations_redirected), color: C.text },
  ]) + 18

  /* incident information */
  y = startSection(doc, y, 'INCIDENT INFORMATION', 130)
  y = infoRows(doc, y, [
    ['Incident ID', incidentId],
    ['Incident Status', status.word],
    ['Campuses At Risk', atRisk.length
      ? atRisk.slice(0, 3).map((s) => `${s.campus} ${s.resource} (${Math.round(s.hours_to_empty)} h)`).join(', ')
      : 'None'],
    ['Road Condition', blocked.length ? `${blocked.length} road(s) blocked` : 'No blockage reported'],
    ['Transfer Status', latest || 'No transfers'],
    ['Report Generated', generated],
  ]) + 10

  /* stock status */
  y = startSection(doc, y, 'STOCK STATUS', tableMin(stocks.length))
  y = dataTable(doc, y + 7, ['CAMPUS', 'RESOURCE', 'STOCK', 'HOURS LEFT', 'STATUS'],
    stocks.map((s) => [
      s.campus, cap(s.resource),
      s.capacity ? `${n0(s.quantity)} / ${qty(s.capacity, s.unit)}` : qty(s.quantity, s.unit),
      s.hours_to_empty >= 999 ? 'N/A' : `${s.hours_to_empty} h`,
      cap(s.status),
    ]),
    [100, 100, 130, 90, CW - 420],
    { colorCol: 4, colors: { red: C.red, amber: C.amber, green: C.green } }) + 18

  /* vehicle tracking */
  y = startSection(doc, y, 'VEHICLE TRACKING', tableMin(vehicles.length))
  y = dataTable(doc, y + 7, ['VEHICLE', 'STATUS', 'BASE CAMPUS', 'CAPACITY'],
    vehicles.map((v) => [v.name, v.available ? 'Available' : 'Unavailable', v.campus, n0(v.capacity)]),
    [130, 120, 140, CW - 390],
    { colorCol: 1, colors: { available: C.green, unavailable: C.red } }) + 18

  /* dispatch & resource movement */
  y = startSection(doc, y, 'DISPATCH & RESOURCE MOVEMENT', tableMin(transfers.length))
  const byTime = (a, b) => (a.created_at < b.created_at ? -1 : 1)
  y = dataTable(doc, y + 7, ['TIME', 'STATUS', 'TRANSFER DETAILS'],
    [...transfers].sort(byTime).map((t) => [
      fmtTime(t.created_at), cap(t.status),
      `${qty(t.quantity, t.unit)} ${t.resource}: ${t.from_campus} -> ${t.to_campus}`
        + (t.distance_km ? ` • ${t.distance_km} km, ETA ${Math.round(t.eta_minutes)} min` : ''),
    ]),
    [90, 100, CW - 190],
    { colorCol: 1, colors: { declined: C.red, received: C.green } }) + 18

  /* donations */
  if (donations.length) {
    y = startSection(doc, y, 'DONATIONS & REDIRECTS', tableMin(donations.length))
    y = dataTable(doc, y + 7, ['TIME', 'DONOR', 'DETAILS'],
      [...donations].sort(byTime).map((d) => [
        fmtTime(d.created_at), d.donor_name,
        `${n0(d.quantity)} ${d.resource}: ` + (d.redirected
          ? `intended ${d.intended_campus} -> redirected to ${d.redirected_campus}`
          : `delivered to ${d.redirected_campus || d.intended_campus || 'N/A'}`),
      ]),
      [90, 110, CW - 200]) + 18
  }

  /* activity timeline */
  y = startSection(doc, y, 'INCIDENT ACTIVITY TIMELINE', tableMin(log.length))
  y = dataTable(doc, y + 7, ['TIME', 'EVENT', 'DETAILS'],
    [...log].sort(byTime).map((e) => [fmtTime(e.created_at), e.action, e.note ? `${e.summary} • ${e.note}` : e.summary]),
    [90, 100, CW - 190]) + 18

  /* response status */
  y = startSection(doc, y, 'RESPONSE STATUS', 110)
  y = infoRows(doc, y, [
    ['Incident', status.word],
    ['Resources Dispatched', n0(dispatched.length)],
    ['Transfers In Transit', n0(inTransit.length)],
    ['Open Requests', n0(requests.length)],
    ['Road Blockage', blocked.length ? blocked.join(', ') : 'Not reported'],
  ]) + 14

  /* closing block */
  y = ensureSpace(doc, y, 52)
  doc.setFillColor(...C.navy)
  doc.roundedRect(M, y, CW, 51, 5, 5, 'F')
  doc.setTextColor(...C.white).setFont('helvetica', 'bold').setFontSize(10)
  doc.text('ResQFlow', M + 13, y + 20)
  doc.setFont('helvetica', 'normal').setFontSize(7.5).setTextColor(...C.pale)
  doc.text('Coordinated Response. Better Prepared Communities.', M + 13, y + 36)

  /* footer + page numbers on every page */
  const total = doc.getNumberOfPages()
  for (let i = 1; i <= total; i++) {
    doc.setPage(i)
    doc.setDrawColor(...C.line).setLineWidth(0.7)
    doc.line(M, FOOT_LINE, PAGE_W - M, FOOT_LINE)
    doc.setFont('helvetica', 'normal').setFontSize(8).setTextColor(...C.slate)
    doc.text('CONFIDENTIAL • OPERATIONAL REPORT', M, 815)
    doc.text(`PAGE ${i} OF ${total}`, PAGE_W - M, 815, { align: 'right' })
  }
  return doc
}

export function downloadIncidentReport(data) {
  const doc = buildIncidentReport(data)
  doc.save(`ResQFlow_Incident_Report_${Date.now()}.pdf`)
}