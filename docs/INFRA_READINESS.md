# VettedCare infrastructure checklist (no Manus required)

Work through these **in order**. None require live operations, real clinicians, or a Manus account.

| # | Task | How to verify | Status |
|---|------|---------------|--------|
| 1 | **Pre-flight script** | `scripts/vettedcare-preflight.ps1` → all required checks pass | ☐ |
| 2 | **Health endpoint** | `GET http://127.0.0.1:8000/health/vettedcare` → `"status": "infra_ready"` | ☐ |
| 3 | **Slim env template** | Copy `.env.vettedcare.example` → compare with your `.env` | ☐ |
| 4 | **Database + migration** | `alembic upgrade head` — table `vettedcare_audit_log` exists | ☐ |
| 5 | **Admin safety dashboard** | http://127.0.0.1:8000/admin — Credential Safety + Infra panels load | ☐ |
| 6 | **Portal safety status** | http://127.0.0.1:8000/portal — login → Credential safety status shows | ☐ |
| 7 | **Simulated Manus webhook** | `scripts/test-manus-webhook.ps1` — POST test without Manus account | ☐ |
| 8 | **Automated tests** | `pytest tests/test_vetted_status.py tests/test_manus_work_queue.py tests/test_vetted_infrastructure.py` | ☐ |
| 9 | **Docker stack** (optional) | `docker compose up -d` — both healthchecks green | ☐ |
| 10 | **Manus hook docs** | Read `docs/MANUS_DAILY_WORKFLOW.md` — ready when Manus account exists | ☐ |

## Not required until go-live (later)

| Task | When |
|------|------|
| Manus worker account + scheduled task | After Manus is ready |
| Twilio live (`SMS_DRY_RUN=false`) | When sending real SMS alerts |
| SMTP live (`EMAIL_DRY_RUN=false`) | When sending real email alerts |
| MBON/OIG/Judiciary live | When running real license checks |
| Cloud host + HTTPS | When leaving localhost |
| Clinician triage / operational vetting | When going operational |

## Three roles (reminder)

| Role | Who | Infra responsibility |
|------|-----|----------------------|
| Operator | You | Approve checklist, set `.env`, decide go-live timing |
| Engineer | Cursor | Platform, API, admin, portal, tests |
| Worker | Manus | Autonomous checks (later — hook is ready now) |

## Quick commands

```powershell
cd C:\OfferCare.ai\offercare-backend

# Start platform
..\start-all.bat   # or desktop VettedCare.ai shortcut

# Pre-flight
.\scripts\vettedcare-preflight.ps1

# Tests
$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\pytest.exe tests/test_vetted_infrastructure.py tests/test_vetted_status.py tests/test_manus_work_queue.py -q

# Simulate Manus (no Manus account)
.\scripts\test-manus-webhook.ps1
```

## Current session progress

Items **1–8** are being built in code now. After API restart, run the pre-flight script to mark them complete.
