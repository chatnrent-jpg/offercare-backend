# Manus → VettedCare webhook



Manus runs autonomous credential checks. VettedCare stores results, computes the final safety status, writes the audit log, and sends alerts.



**Manus acts. VettedCare decides.**



Full daily loop: [MANUS_DAILY_WORKFLOW.md](./MANUS_DAILY_WORKFLOW.md)



## Manus worker endpoints



All require header `X-Manus-Key: <MANUS_API_KEY>`.



| Method | Path | Purpose |

|--------|------|---------|

| GET | `/api/vettedcare/manus/config` | Integration map for Manus |

| GET | `/api/vettedcare/manus/work-queue` | Who to vet today |

| GET | `/api/vettedcare/manus/providers/{id}` | Single work order + lookup fields |

| POST | `/api/vettedcare/manus/run` | Submit one vetting run |

| POST | `/api/vettedcare/manus/batch` | Submit many runs + optional safety cycle |



## Submit results



```

POST http://127.0.0.1:8000/api/vettedcare/manus/run

Header: X-Manus-Key: <MANUS_API_KEY from .env>

Content-Type: application/json

```



## Example payload



```json

{

  "run_id": "manus-daily-2026-06-24-001",

  "npi_number": "1234567890",

  "summary": "Daily MBON + OIG re-check",

  "recommended_status": "CLEAR",

  "run_full_screen": false,

  "checks": [

    {

      "check_type": "MBON",

      "result": "PASS",

      "source_url": "https://mbon.maryland.gov/",

      "notes": "RN license active through 2027-04-01"

    },

    {

      "check_type": "OIG",

      "result": "CLEAR",

      "source_url": "https://exclusions.oig.hhs.gov/",

      "notes": "No LEIE match"

    },

    {

      "check_type": "JUDICIARY",

      "result": "PASS",

      "notes": "No open disciplinary case"

    }

  ]

}

```



## Provider lookup (first match wins)



1. `provider_id` (UUID)

2. `npi_number`

3. `email`

4. `md_license_number`



## Check types mapped to screenings



| Manus check_type | VettedCare screening |

|------------------|----------------------|

| OIG, OIG_LEIE     | OIG                  |

| MBON              | MBON                 |

| JUDICIARY, MD_JUDICIARY | JUDICIARY      |



## Result values



**Pass:** `PASS`, `CLEAR`, `OK`, `VERIFIED`



**Fail:** `FAIL`, `BLOCKED`, `EXCLUDED`, `DENIED`, `FLAGGED`



**Pending:** `UNKNOWN`, `PENDING`, `REVIEW`



## After ingest



VettedCare will:



1. Store the run in `manus_vetting_runs`

2. Append license verification log entries

3. Recompute `CLEAR | EXPIRING | ACTION_NEEDED | BLOCKED`

4. Write an audit event

5. Send SMS/email alerts when status is EXPIRING, ACTION_NEEDED, or BLOCKED



`recommended_status` from Manus is logged for review but **does not override** the computed status.



## curl test



```powershell

$key = "YOUR_MANUS_KEY"

curl.exe -s "http://127.0.0.1:8000/api/vettedcare/manus/work-queue?limit=5" -H "X-Manus-Key: $key"

curl.exe -X POST "http://127.0.0.1:8000/api/vettedcare/manus/run" `

  -H "Content-Type: application/json" `

  -H "X-Manus-Key: $key" `

  -d "@docs/manus-webhook-example.json"

```


