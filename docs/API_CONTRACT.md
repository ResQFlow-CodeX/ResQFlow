# ResQFlow API Contract (v1)
Base URL: `http://localhost:8000/api`. All bodies are JSON. Share this file with every AI tool and teammate.

## Conventions
- Quantities are numbers; units come from the resource (`water` = L, `medicine` = units).
- `status` of a campus-resource: `green` (> 24 h), `amber` (12-24 h), `red` (< 12 h).
- Transfer status flow: `suggested -> approved -> dispatched -> received` (or `declined`).

## GET /campuses
```json
[{
  "id": 1, "name": "Campus A", "lat": 12.9386, "lng": 77.7220,
  "stocks": [{
    "resource": "water", "unit": "L", "quantity": 1800, "safety_reserve": 500,
    "consumption_rate": 60, "hours_to_empty": 30.0, "status": "green"
  }]
}]
```

## GET /recommendations
Engine output, ranked most urgent first. Not saved until the coordinator acts on it.
```json
[{
  "key": "water:3->1", "priority_score": 87.5,
  "resource": "water", "unit": "L", "quantity": 2000,
  "from_campus": {"id": 2, "name": "Campus B", "lat": 12.9719, "lng": 77.6412},
  "to_campus": {"id": 1, "name": "Campus A", "lat": 12.9386, "lng": 77.7220},
  "vehicle": "Tanker 1",
  "distance_km": 14.2, "eta_minutes": 38, "route": [[12.97, 77.64], [12.95, 77.68], [12.93, 77.72]], "route_source": "osrm",
  "feasible": true,
  "reasons": [
    "Campus A water projected to last about 6 hours.",
    "Campus B can supply 2,000 L while keeping its 1,500 L safety reserve.",
    "Road reported open; Tanker 1 (3,000 L) available; ETA 38 min."
  ]
}]
```

## POST /transfers  (coordinator acts on a recommendation)
Request: `{"from_campus_id":2,"to_campus_id":1,"resource":"water","quantity":2000,"reasons":["..."],"action":"approve"}`
`action`: `approve` | `modify` | `decline`. **modify** = approve with an edited `quantity` (add a `note`). `note` is optional.
Response: the transfer
```json
{"id": 7, "status": "approved", "from_campus_id": 2, "to_campus_id": 1,
 "resource": "water", "quantity": 2000, "reasons": ["..."], "eta_minutes": 38}
```

## GET /transfers
List of transfers (same shape as above), newest first.

## POST /transfers/{id}/advance
Moves `approved -> dispatched -> received`. Donor stock is debited at dispatch; recipient stock is credited at receipt. Returns the transfer.

## POST /requests
`{"campus_id":3,"resource":"medicine","quantity":30,"deadline_hours":4}` -> created request.

## GET /requests
Open requests with `campus`, `resource`, `quantity`, `deadline_hours`.

## POST /donations
`{"donor_name":"Acme CSR","resource":"water","quantity":1000,"intended_campus_id":1}`
Response:
```json
{"accepted_as_intended": false,
 "redirected_campus": {"id": 3, "name": "Campus C"},
 "message": "Campus A's water need is already covered by a pending transfer. Campus C still needs water."}
```

## POST /simulate/disaster
Request: `{"campus_id":1,"disaster_type":"flood"}`. Supported types: `flood`, `earthquake`, `cyclone`, `drought`. Only the selected campus is affected. The original no-body request remains supported as the Campus A flood demo.

## POST /simulate/reset
Resets all data to the seed state. Returns `{"ok": true}`.

## GET /log
Decision audit trail: `[{"transfer_id":7,"action":"approve","note":"...","created_at":"..."}]`

## POST /roads
Report a road closed or open: `{"from_campus_id":2,"to_campus_id":1,"blocked":true}`. Blocked roads make transfers `feasible: false`. Cleared by `/simulate/reset`.

## Notes
- `/recommendations` already counts approved/dispatched transfers as arriving, so approving one removes it from the list.
- Approved transfers reserve donor stock. Stock is debited once at `dispatched` and credited once at `received`.
- Donation offers are credited immediately to the selected or redirected campus. Offers exceeding free storage capacity are rejected.
- Interactive docs for every endpoint: http://127.0.0.1:8000/docs

## Routing (Module 5)
`route` is a list of `[lat, lng]` points for the map. `route_source` is `"osrm"` (real roads) or `"estimate"` (straight line, used when offline).
Non-declined transfers retain route geometry for tracking. Transfer records include `distance_km`, `eta_minutes`, `route_source`, `created_at`, `dispatched_at`, `received_at`, and `estimated_arrival_at` (projected from approval time, then recalculated from dispatch time).

## Capture, vehicles, SMS (Module 6)
- `POST /inventory` `{"campus_id":1,"resource":"water","quantity":500,"consumption_rate":20,"safety_reserve":200,"expiry_days":30}`: every field except campus and resource is optional, send only what changed.
- `POST /sms` `{"text":"A water 500"}`: mock SMS fallback, sets Campus A water stock to 500. Returns `{"ok":true,"message":"..."}`.
- `GET /vehicles`, `POST /vehicles/{id}/availability` `{"available":false}`: an unavailable fleet makes transfers infeasible.
- `GET /roads`: `{"blocked_roads":[[1,2]]}`.
- `GET /donations`: history, with `redirected: true` when the donation was sent somewhere other than intended.
- `GET /impact`: `water_redirected_l, medicine_redirected_units, transfers_completed, transfers_in_progress, transfers_declined, donations_total, donations_redirected, decisions_logged`.
- `GET /forecast?hours=24`: `{"hours":[0..24],"series":[{"campus","resource","unit","values":[...],"runs_out_in":6.0}]}`.
- `GET /campuses` stocks now include `expiry_days` (days until expiry, or null).

## v6.1 inventory and campus fields
- `GET /campuses` now returns `disaster_type` per campus and `storage_capacity` per inventory item.
- Inventory stock plus outstanding inbound transfers cannot exceed `storage_capacity`.
- Approved outbound transfers reserve stock; manual stock edits cannot reduce stock below approved reservations.
- `POST /inventory` rejects stock values above capacity.
- `POST /inventory/consume` accepts `{"campus_id":1,"resource":"water","hours":1}` and immediately reduces persisted stock by the current consumption rate, clamped at zero.
