# Manus B2B Facility Recruitment Engine

**Manus acts · VettedMe decides.**

Hybrid split: Manus runs external web workflows (RFP monitors, LinkedIn/directory enrichment, VMS logins). Cursor/VettedMe parses, dedupes, matches, and gates dispatch locally.

## Filesystem handoff

| Path | Owner | Purpose |
|------|-------|---------|
| `data_engine/raw_leads/` | Manus → Cursor | CSV with required lead fields |
| `data_engine/incoming_contracts/` | Operator/Manus drop | PDF/DOCX/TXT MSAs |
| `data_engine/incoming_shifts/` | Manus drop | VMS open-shift JSON batches |

## Manus API (`X-Manus-Key`)

| Method | Endpoint |
|--------|----------|
| GET | `/api/vettedcare/manus/recruitment/config` |
| POST | `/api/vettedcare/manus/recruitment/leads/import` `{ "csv_filename": "leads.csv" }` |
| POST | `/api/vettedcare/manus/recruitment/shifts` `{ "shifts": [ ... ] }` |
| POST | `/api/vettedcare/manus/recruitment/contracts/process` |

## Lead CSV required columns

- `facility_name`
- `contact_role` (CNO, DON, HR VP, …)
- `email_domain`
- `procurement_urgency`
- `source_url`

## Shift JSON required fields

- `facility_id` (UUID from `maryland_facilities`)
- `shift_date`, `unit_dept`, `start_time`
- `shift_role`, `hourly_pay_rate`

Dedupe key: `hash(facility_id + shift_date + unit_dept + start_time)`

On new shift ingest → `lookahead_shift_matcher.py` returns top 3 VETTED_CLEAR nurses.

## Contract safety gate

Parsed MSAs with margin below `CONTRACT_MIN_MARGIN_PCT` (default 18%) → `PENDING_EXECUTIVE_REVIEW` + `dispatch_halted=true`.

## Database

Run migration:

```powershell
cd C:\VettedMe.ai\vettedcare-backend
alembic upgrade head
```

Reference SQL: `data_engine/migrations/002_facility_recruitment.sql`

Tables: `facility_contracts`, `b2b_raw_leads`, `ingested_open_shifts`

## Local processing (Cursor)

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -c "from data_engine.contract_processor import process_incoming_contracts_dir; ..."
python -c "from data_engine.shift_ingest import ingest_shifts_from_directory; ..."
```
