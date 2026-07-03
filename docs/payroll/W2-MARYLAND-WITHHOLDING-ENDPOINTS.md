# W-2 Maryland Withholding — Endpoint Reference

Focused endpoint map for **federal**, **Maryland state**, and **Maryland county/local** income tax withholding for W-2 employees. Maps to VettedCare `caregiver_w2_employee_accounts.maryland_residence_county`.

Sources: mirrored files under `docs/payroll/gusto/` and `docs/payroll/checkhq/`.

---

## Maryland county tax model (both providers)

| Fact | Gusto | Check HQ |
|------|-------|----------|
| County tax basis | Employee **home address** county | Employee residence + workplaces drive jurisdiction params |
| Filing | County tax bundled with MD state income tax to Comptroller | Local MD taxes use jurisdiction code `md` (state + local grouped) |
| VettedCare field | `maryland_residence_county` on W-2 account | Same — feed into employee home address / tax params before calc |

See: `gusto/gusto-maryland-county-withholding-notes.md` (County taxes section).

---

## Gusto Embedded Payroll

Base URL (demo): `https://api.gusto-demo.com`  
Base URL (production): `https://api.gusto.com`  
Auth: `Authorization: Bearer {COMPANY_API_TOKEN}`  
Version header: `X-Gusto-API-Version: 2024-04-01` (or newer per docs)

### 1. Configure withholding inputs (before calculation)

| Step | Method | Endpoint | Scope | Local file |
|------|--------|----------|-------|------------|
| Get employee W-4 (federal) | `GET` | `/v1/employees/{employee_uuid}/federal_taxes` | `employee_federal_taxes:read` | `gusto/gusto-get-employee-federal-taxes.md` |
| Update employee W-4 | `PUT` | `/v1/employees/{employee_uuid}/federal_taxes` | `employee_federal_taxes:write` | `gusto/gusto-put-employee-federal-taxes.md` |
| Get MD state tax questions | `GET` | `/v1/employees/{employee_uuid}/state_taxes` | `employee_state_taxes:read` | `gusto/gusto-get-employee-state-taxes.md` |
| Update MD state tax answers | `PUT` | `/v1/employees/{employee_uuid}/state_taxes` | `employee_state_taxes:write` | `gusto/gusto-put-employee-state-taxes.md` |
| Set employee home address (county) | `GET` | `/v1/employees/{employee_uuid}/home_addresses` | `employees:read` | `gusto/gusto-get-employee-home-addresses.md` |
| Create/update home address | `POST` / `PUT` | `/v1/employees/{employee_uuid}/home_addresses` | `employees:write` | `gusto/gusto-post-employee-home-address.md` |
| Company MD tax registration | `GET` | `/v1/companies/{company_uuid}/tax_requirements/MD` | `company_tax_requirements:read` | `gusto/gusto-get-state-tax-requirements.md` |
| Update company MD tax setup | `PUT` | `/v1/companies/{company_uuid}/tax_requirements/MD` | `company_tax_requirements:write` | `gusto/gusto-put-state-tax-requirements.md` |

Guide: `gusto/gusto-configure-employee-tax-information.md`

**Maryland note:** State tax API returns question/answer metadata per state. For MD employees, home address county drives county add-on to state withholding at payroll calculation time.

### 2. Calculate withholdings (payroll run preview)

| Step | Method | Endpoint | Scope | Local file |
|------|--------|----------|-------|------------|
| Calculate taxes/benefits/deductions | `PUT` | `/v1/companies/{company_id}/payrolls/{payroll_id}/calculate` | `payrolls:run` | `gusto/gusto-calculate-payroll.md` |
| Poll calculated results | `GET` | `/v1/companies/{company_id}/payrolls/{payroll_id}?include=taxes,benefits,deductions` | `payrolls:read` | `gusto/gusto-get-payroll-with-taxes.md` |

Flow (async):

1. `PUT .../calculate` → `202 Accepted`
2. Poll `GET .../payrolls/{id}?include=taxes,benefits,deductions` until `calculated_at` is populated
3. Read per-employee tax lines from `employee_compensations` and `totals`

Guide: `gusto/gusto-complete-a-regular-payroll.md` (section 3)

### 3. Federal + MD + county on pay stub

Gusto returns calculated tax amounts in the payroll object after calculation. Maryland county amounts are **included in Maryland state income tax withholding**, not as a separate line item in all views.

---

## Check HQ

Base URL (sandbox): `https://sandbox.checkhq.com`  
Base URL (production): `https://api.checkhq.com`  
Auth: `Authorization: Bearer {API_KEY}`

Maryland jurisdiction code: **`md`** (includes state and local taxes — see `checkhq/checkhq-jurisdictions.md`).

### 1. Configure withholding inputs (before calculation)

| Step | Method | Endpoint | Local file |
|------|--------|----------|------------|
| List employee tax parameters | `GET` | `/employee_tax_params/{employee_id}?jurisdiction=md` | `checkhq/checkhq-list-employee-tax-parameters.md` |
| Update employee tax parameters | `PATCH` | `/employee_tax_params/{employee_id}` | `checkhq/checkhq-update-employee-tax-parameters.md` |
| List effective-dated settings | `GET` | `/employee_tax_params/{employee_id}/settings?jurisdiction=md` | `checkhq/checkhq-list-employee-tax-parameter-settings.md` |
| Get one parameter setting | `GET` | `/employee_tax_params/{employee_id}/settings/{tax_param_id}` | `checkhq/checkhq-get-employee-tax-parameter-setting.md` |
| Bulk list params (company) | `GET` | `/employee_tax_params?company={company_id}&jurisdiction=md` | `checkhq/checkhq-bulk-get-employee-tax-params.md` |
| Bulk update params | `PATCH` | `/employee_tax_params` | `checkhq/checkhq-bulk-update-employee-tax-parameters.md` |
| Employee W-4 / state forms (UI) | Component | Employee Withholdings Setup | `checkhq/checkhq-employee-withholdings-setup.md` |
| Tax elections (legacy) | `GET` / `PATCH` | `/employee_tax_elections/{employee_id}` | `checkhq/checkhq-employee-tax-elections.md` |

Guide: `checkhq/checkhq-tax-parameters.md`

**Maryland local:** Filter tax catalog with `jurisdiction=md` — local taxes share the `md` jurisdiction code (`checkhq/checkhq-taxes-and-agencies.md`).

### 2. Calculate withholdings (payroll preview / approve)

| Step | Method | Endpoint | Local file |
|------|--------|----------|------------|
| Preview payroll (calc taxes) | `POST` | `/payrolls/{payroll_id}/preview` | `checkhq/checkhq-preview-payroll.md` |
| Approve payroll (final calc) | `POST` | `/payrolls/{payroll_id}/approve` | `checkhq/checkhq-approve-payroll.md` |
| Read tax lines per employee | `GET` | payroll item → `taxes[]` | `checkhq/checkhq-the-payroll-item-object.md` |
| List tax catalog (MD SIT/local) | `GET` | `/taxes?jurisdiction=md&label_contains=...` | `checkhq/checkhq-list-taxes.md` |

Guide: `checkhq/checkhq-calculating-payroll-taxes.md`

Each payroll item `taxes[]` entry:

```json
{
  "tax": "tax_...",
  "description": "Maryland State Tax",
  "amount": "123.45",
  "payer": "employee"
}
```

### 3. Overrides (FIT + SIT only — not county/local directly)

| Step | Method | Field | Local file |
|------|--------|-------|------------|
| Override FIT/SIT on one pay run | `PATCH` | payroll item `tax_overrides[]` | `checkhq/checkhq-overriding-withholding-taxes.md` |

**Limitation:** Overrides apply to Federal Income Tax and State Income Tax only — not FICA, SUI, or local taxes.

### 4. Multi-state / reciprocity

If caregivers work in one MD county and live in another state: `checkhq/checkhq-multi-state-withholdings.md`

---

## Recommended VettedCare call sequence (Tier 1 W-2)

```
1. caregiver profile created (MBON + employment_tier=TIER1_W2)
2. W-2 account created with maryland_residence_county
3. Sync to payroll provider:
   a. Employee home address → county
   b. Federal W-4 params
   c. MD state tax params (provider-specific questions)
   d. Company MD tax requirements (CRN, filing frequency)
4. Create/prepare payroll with earnings
5. Calculate / preview payroll
6. Read back federal + MD (incl. county) withholding amounts
7. Store results on shift payout / timesheet record
```

---

## Full doc indexes

- `gusto/llms-index.txt` — 646 lines, all Gusto Embedded Payroll pages
- `checkhq/llms-index.txt` — 317 lines, all Check HQ pages
