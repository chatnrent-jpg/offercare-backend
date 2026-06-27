# Manus daily recruitment routine

**Manus acts · VettedCare decides.**

## 1. Export (PowerShell)

```powershell
cd C:\VettedCare.ai\vettedcare-backend
$env:PYTHONPATH = (Get-Location).Path
python export_manus_recruitment.py
```

Output: `logs\manus\recruitment_snapshot.json`

## 2. Manus task

1. Open your **VettedCare** Manus project → **New Task**
2. Attach `recruitment_snapshot.json`
3. Send:

```
Read the attached recruitment_snapshot.json. Report:
- Contracts in PENDING_EXECUTIVE_REVIEW (do not recommend dispatch)
- High-urgency B2B leads
- Unprocessed files in drop_zones (raw_leads_csv, incoming_contracts, incoming_shifts_json)
- Today's Manus tasks: RFP/RFQ monitoring, CNO/DON enrichment, VMS open-shift sync
```

## 3. Manus outputs → VettedCare drop zones

| Manus delivers | Drop here |
|----------------|-----------|
| Lead CSV | `data_engine/raw_leads/` |
| Staffing MSA PDF/DOCX | `data_engine/incoming_contracts/` |
| VMS shift JSON | `data_engine/incoming_shifts/` or POST `/api/vettedcare/manus/recruitment/shifts` |

## 4. Cursor processes (admin or API)

Admin console → **Facility recruitment engine** → Process buttons

Or:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/vettedcare/recruitment/leads/import-all -H "X-Admin-Key: YOUR_KEY"
curl.exe -X POST http://127.0.0.1:8000/api/vettedcare/recruitment/contracts/process -H "X-Admin-Key: YOUR_KEY"
curl.exe -X POST http://127.0.0.1:8000/api/vettedcare/recruitment/shifts/process-dir -H "X-Admin-Key: YOUR_KEY"
```

## 5. Pass check

- High-urgency leads appear in admin recruitment panel
- Contracts with low margin show **PENDING_EXECUTIVE_REVIEW**
- New VMS shifts dedupe and show top 3 nurse matches

See also: `docs/MANUS_B2B_RECRUITMENT.md`
