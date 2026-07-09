# VettedMe + Manus daily workflow

**You operate. Cursor builds. Manus works.**

| Role | Who | Responsibility |
|------|-----|----------------|
| Operator | You | Priorities, alert rules, exceptions |
| Engineer | Cursor | VettedMe API, admin, audit, status engine |
| Worker | Manus | Fetch queue, run checks, POST evidence |

**Manus acts. VettedMe decides.**

---

## Step 0 — one-time setup

1. Start VettedMe: double-click **VettedMe** on your desktop.
2. In `.env`, set:
   - `MANUS_API_KEY` — shared secret for Manus only
   - `PUBLIC_BASE_URL=http://127.0.0.1:8000` (or your public URL later)
3. In Manus, store the same `MANUS_API_KEY` as a secret.

---

## Step 1 — Manus discovers the integration

```http
GET /api/vettedcare/manus/config
X-Manus-Key: <MANUS_API_KEY>
```

Returns all endpoints, required checks (`MBON`, `OIG`, `JUDICIARY`), and limits.

---

## Step 2 — Manus pulls today's work queue

```http
GET /api/vettedcare/manus/work-queue?limit=25&queue=due
X-Manus-Key: <MANUS_API_KEY>
```

**Queue modes**

| queue | Who is included |
|-------|-----------------|
| `due` (default) | BLOCKED, EXPIRING, ACTION_NEEDED, stale CLEAR |
| `blocked` | BLOCKED only |
| `expiring` | EXPIRING only |
| `action_needed` | ACTION_NEEDED only |
| `stale_clear` | CLEAR profiles due for re-verification |
| `all` | Full sweep (respects min re-run window) |

Each item includes `provider_id`, lookup fields, priority, and `work_order_url`.

---

## Step 3 — Manus fetches a work order (optional detail)

```http
GET /api/vettedcare/manus/providers/{provider_id}
X-Manus-Key: <MANUS_API_KEY>
```

Returns exact lookup data and a `submit.body_template` Manus fills in after checks.

---

## Step 4 — Manus runs checks (worker tasks)

For each clinician, Manus autonomously:

1. **MBON** — verify Maryland license matches name/number
2. **OIG** — search LEIE exclusions (name + NPI)
3. **JUDICIARY** — search disciplinary / judiciary records

Manus collects evidence URLs and short notes for each check.

---

## Step 5 — Manus submits results

Single clinician:

```http
POST /api/vettedcare/manus/run
X-Manus-Key: <MANUS_API_KEY>
Content-Type: application/json
```

Body: see `docs/manus-webhook-example.json`

Batch (after a daily loop):

```http
POST /api/vettedcare/manus/batch
X-Manus-Key: <MANUS_API_KEY>
```

```json
{
  "run_cycle_after": true,
  "runs": [ { "...": "one ManusVettingRunIn per clinician" } ]
}
```

VettedMe then:

- Stores the run
- Recomputes **CLEAR / EXPIRING / ACTION NEEDED / BLOCKED**
- Writes audit events
- Sends alerts when required

Manus `recommended_status` is logged but **never overrides** VettedMe.

---

## Step 6 — You review (operator)

Open **http://127.0.0.1:8000/admin**

- Credential Safety Dashboard
- Recent safety audit
- Recent alerts

Approve exceptions or adjust rules — Manus keeps running on schedule.

---

## Manus task prompt (paste into Manus)

```
You are the VettedMe.ai autonomous vetting worker.

Base URL: http://127.0.0.1:8000
Auth header: X-Manus-Key: <your key>

Daily loop:
1. GET /api/vettedcare/manus/work-queue?limit=25&queue=due
2. For each item, GET work_order_url if you need lookup details
3. Run MBON, OIG, and JUDICIARY checks using the lookup fields
4. POST /api/vettedcare/manus/run with check evidence for each provider
5. Optionally POST /api/vettedcare/manus/batch with run_cycle_after=true

Rules:
- Submit factual evidence only (source URLs + notes)
- Do not invent pass/fail results
- VettedMe computes final safety status — you do not override it
- Skip providers you cannot verify; use result PENDING with notes
```

---

## curl smoke test

```powershell
$key = "YOUR_MANUS_KEY"
curl.exe -s "http://127.0.0.1:8000/api/vettedcare/manus/config" -H "X-Manus-Key: $key"
curl.exe -s "http://127.0.0.1:8000/api/vettedcare/manus/work-queue?limit=3" -H "X-Manus-Key: $key"
```

See also: [MANUS_WEBHOOK.md](./MANUS_WEBHOOK.md)
