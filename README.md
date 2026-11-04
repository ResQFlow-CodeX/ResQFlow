# ResQFlow v6.1 prototype
```
resqflow/
  docs/API_CONTRACT.md   # shared contract (frontend + backend)
  backend/               # FastAPI + SQLAlchemy (SQLite now, PostgreSQL later)
    database.py  models.py  seed.py  requirements.txt
    engine.py  test_engine.py   # Module 2: decision engine + tests (run: pytest -v)
    main.py  test_api.py  test_api_extra.py   # Modules 3 and 6: API + tests
    routing.py  test_routing.py # Module 5: OSRM road routing with offline fallback
  frontend/              # React: sidebar app with Overview, Campuses, Requests, Donors, Reports
```
## Run
```
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python seed.py
```

## Start the API
```
uvicorn main:app --reload      # then open http://127.0.0.1:8000/docs
```

## Start the frontend (second terminal window)
```
cd frontend
npm install        # first time only
npm run dev        # then open http://localhost:5173
```
The backend (uvicorn) must be running at the same time.

## v6.1 notes
- Water inventory has per-campus storage capacity checks. Stock edits, donations and inbound transfers cannot exceed capacity.
- Donations are credited to the selected/redirected campus immediately; over-capacity offers are rejected with the available space.
- Campus inventory includes an instant one-hour consumption simulation control; the backend subtracts the current consumption rate and never allows stock below zero.
- Transfers reserve approved donor stock, debit it once at dispatch, and credit the receiver once at receipt. Dispatch and receipt timestamps are stored.
- Disaster simulation accepts `campus_id` and `disaster_type` (`flood`, `earthquake`, `cyclone`, `drought`). Only that campus is affected. The no-body endpoint remains supported as the original Campus A flood demo.
- OSRM routing and its offline estimate fallback remain in place. Transfer records expose route, distance, ETA, dispatch time and estimated arrival.
- The backend adds lightweight additive SQLite column migrations at startup for existing v6 databases. Legacy water rows receive a conservative demo storage headroom during migration because v6 did not store capacities.

## Verification
From `backend/`, run `python -m pytest -v`. The v6.1 regression suite includes campus-scoped disasters, inventory capacity, donation crediting, transfer reservation and exactly-once dispatch/receipt accounting.
# ResQFlow
A disaster response and resource coordination platform built with React and FastAPI.
