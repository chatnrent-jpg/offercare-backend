# Payroll API Documentation Mirror

Local mirror of **Gusto Embedded Payroll** and **Check HQ** developer documentation, focused on W-2 employee tax withholding (federal, Maryland state, and Maryland county/local).

Downloaded: 2026-07-02 from official doc indexes:

- Gusto: https://docs.gusto.com/llms.txt
- Check HQ: https://docs.checkhq.com/llms.txt

## Folder layout

```
docs/payroll/
├── README.md
├── W2-MARYLAND-WITHHOLDING-ENDPOINTS.md   ← start here (VettedMe mapping)
├── gusto/
│   ├── llms-index.txt                     ← full Gusto doc index
│   └── *.md                               ← mirrored guides + endpoint refs
└── checkhq/
    ├── llms-index.txt                     ← full Check HQ doc index
    └── *.md                               ← mirrored guides + endpoint refs
```

## VettedMe integration context

Our Tier 1 W-2 caregiver accounts store `maryland_residence_county` on `caregiver_w2_employee_accounts` because Maryland **county income tax is based on the employee's home address**, not work location (Gusto support docs). Both providers fold county withholding into Maryland state income tax calculation at payroll run time when home address / tax parameters are configured correctly.

## Quick links

| Topic | Gusto | Check HQ |
|-------|-------|----------|
| Employee federal W-4 | `gusto/gusto-get-employee-federal-taxes.md` | `checkhq/checkhq-employee-tax-elections.md` |
| Employee MD state setup | `gusto/gusto-get-employee-state-taxes.md` | `checkhq/checkhq-list-employee-tax-parameters.md?jurisdiction=md` |
| Run tax calculation | `gusto/gusto-calculate-payroll.md` | `checkhq/checkhq-preview-payroll.md` |
| Read calculated taxes | `gusto/gusto-get-payroll-with-taxes.md` | `checkhq/checkhq-the-payroll-item-object.md` |
| MD county (via home address) | `gusto/gusto-get-employee-home-addresses.md` | `checkhq/checkhq-workplaces.md` + employee address APIs |
| MD county behavior notes | `gusto/gusto-maryland-county-withholding-notes.md` | `checkhq/checkhq-jurisdictions.md` (`md` includes state + local) |

## Refreshing this mirror

From repo root (requires network):

```powershell
.\scripts\sync-payroll-docs.ps1
```

Or re-run the Python fetch block in that script manually.
